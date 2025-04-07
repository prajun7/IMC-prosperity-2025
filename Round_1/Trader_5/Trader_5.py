import json
from typing import List, Dict, Tuple
import numpy as np
import math

# Import necessary datamodel components
from datamodel import OrderDepth, TradingState, Order

# --- Constants and Parameters ---
# Rainforest Resin
RESIN_FAIR_VALUE = 10010
RESIN_SPREAD = 1 # Place orders +/- 1 tick from fair value

# Kelp - Bollinger Bands derived strategy
KELP_BB_WINDOW = 20
KELP_SPREAD_STD_MULT = 0.7 # Spread = ceil(std_dev * MULT), min 1 tick

# Squid Ink - Bollinger Bands derived strategy
SQUID_INK_BB_WINDOW = 20
SQUID_INK_SPREAD_STD_MULT = 1.0 # Wider spread multiplier due to higher volatility

# General
ORDER_SIZE = 10 # Trade fixed size per order instead of full capacity
DEFAULT_POSITION_LIMIT = 20


class Trader:

    POSITION_LIMITS = {
        "RAINFOREST_RESIN": 50,
        "KELP": 50,
        "SQUID_INK": 50,
    }

    # Instance variable for price history (managed via traderData)
    price_history = {}

    def get_position_limit(self, product):
        """Gets the position limit for a given product."""
        return self.POSITION_LIMITS.get(product, DEFAULT_POSITION_LIMIT)

    def calculate_sma_std(self, prices: List[float], window: int) -> Tuple[float, float]:
        """Calculates Simple Moving Average and Standard Deviation."""
        if len(prices) < window:
            return np.nan, np.nan # Not enough data

        relevant_prices = np.array(prices[-window:])
        sma = np.mean(relevant_prices)
        std_dev = np.std(relevant_prices)
        return sma, std_dev

    def update_price_history(self, product: str, price: float, max_len: int):
        """Appends price to history and trims the list."""
        if product not in self.price_history:
            self.price_history[product] = []
        history = self.price_history[product]
        history.append(price)
        if len(history) > max_len:
            self.price_history[product] = history[-max_len:]

    def run(self, state: TradingState) -> Tuple[Dict[str, List[Order]], int, str]:
        """
        Processes TradingState, executes strategies, and returns orders and updated state.
        """
        # --- State Loading ---
        try:
            trader_data_dict = json.loads(state.traderData) if state.traderData else {}
        except json.JSONDecodeError:
            trader_data_dict = {}
        self.price_history = trader_data_dict.get("price_history", {})

        result_orders: Dict[str, List[Order]] = {}

        # --- Strategy Execution Loop ---
        for product in state.order_depths:
            order_depth = state.order_depths.get(product)
            if not order_depth or not order_depth.buy_orders or not order_depth.sell_orders:
                continue

            orders: List[Order] = []
            position_limit = self.get_position_limit(product)
            current_position = state.position.get(product, 0)

            best_bid = max(order_depth.buy_orders.keys())
            best_ask = min(order_depth.sell_orders.keys())

            # Basic sanity check for crossed book
            if best_bid >= best_ask:
                 continue

            mid_price = (best_bid + best_ask) / 2.0

            # Calculate available capacity
            max_buy_capacity = position_limit - current_position
            max_sell_capacity = position_limit + current_position # Positive value

             # Determine actual volume to trade (fixed size, respecting limits)
            buy_order_volume = min(ORDER_SIZE, max_buy_capacity)
            sell_order_volume = min(ORDER_SIZE, max_sell_capacity) # Positive value


            # --- Product-Specific Logic ---

            # 1. Rainforest Resin: Market Making around fixed mean
            if product == "RAINFOREST_RESIN":
                our_buy_price = RESIN_FAIR_VALUE - RESIN_SPREAD
                our_sell_price = RESIN_FAIR_VALUE + RESIN_SPREAD

                # Place BUY order if we have capacity
                if buy_order_volume > 0:
                    orders.append(Order(product, our_buy_price, buy_order_volume))
                    # print(f"PLACING BUY {product}: {buy_order_volume}x at {our_buy_price}")

                # Place SELL order if we have capacity
                if sell_order_volume > 0:
                    # Remember: Sell order quantity must be negative
                    orders.append(Order(product, our_sell_price, -sell_order_volume))
                    # print(f"PLACING SELL {product}: {sell_order_volume}x at {our_sell_price}")

            # 2. Kelp: Market Making around BB SMA with dynamic spread
            elif product == "KELP":
                window = KELP_BB_WINDOW
                spread_mult = KELP_SPREAD_STD_MULT
                max_hist_len = window + 5

                self.update_price_history(product, mid_price, max_hist_len)
                current_product_history = self.price_history.get(product, [])
                sma, std_dev = self.calculate_sma_std(current_product_history, window)

                if not math.isnan(sma) and not math.isnan(std_dev):
                    # Dynamic spread based on std dev, minimum 1 tick
                    spread = max(1, math.ceil(std_dev * spread_mult))
                    our_buy_price = math.floor(sma - spread)
                    our_sell_price = math.ceil(sma + spread)

                    # Place BUY order
                    if buy_order_volume > 0:
                        orders.append(Order(product, our_buy_price, buy_order_volume))
                        # print(f"PLACING BUY {product}: {buy_order_volume}x at {our_buy_price} (SMA: {sma:.2f}, Spread: {spread})")

                    # Place SELL order
                    if sell_order_volume > 0:
                        orders.append(Order(product, our_sell_price, -sell_order_volume))
                        # print(f"PLACING SELL {product}: {sell_order_volume}x at {our_sell_price} (SMA: {sma:.2f}, Spread: {spread})")

            # 3. Squid Ink: Market Making around BB SMA with wider dynamic spread
            elif product == "SQUID_INK":
                window = SQUID_INK_BB_WINDOW
                spread_mult = SQUID_INK_SPREAD_STD_MULT # Use wider multiplier
                max_hist_len = window + 5

                self.update_price_history(product, mid_price, max_hist_len)
                current_product_history = self.price_history.get(product, [])
                sma, std_dev = self.calculate_sma_std(current_product_history, window)

                if not math.isnan(sma) and not math.isnan(std_dev):
                    # Dynamic spread based on std dev, minimum 1 tick
                    spread = max(1, math.ceil(std_dev * spread_mult))
                    our_buy_price = math.floor(sma - spread)
                    our_sell_price = math.ceil(sma + spread)

                    # Place BUY order
                    if buy_order_volume > 0:
                        orders.append(Order(product, our_buy_price, buy_order_volume))
                        # print(f"PLACING BUY {product}: {buy_order_volume}x at {our_buy_price} (SMA: {sma:.2f}, Spread: {spread})")

                    # Place SELL order
                    if sell_order_volume > 0:
                        orders.append(Order(product, our_sell_price, -sell_order_volume))
                        # print(f"PLACING SELL {product}: {sell_order_volume}x at {our_sell_price} (SMA: {sma:.2f}, Spread: {spread})")


            # Add generated orders for the current product
            if orders:
                result_orders[product] = orders

        # --- State Saving ---
        trader_data_dict["price_history"] = self.price_history
        traderData_str = json.dumps(trader_data_dict, separators=(',', ':'))

        conversions = 0
        return result_orders, conversions, traderData_str