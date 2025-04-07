from datamodel import OrderDepth, TradingState, Order
from typing import List, Dict
import json
import math
import statistics # Needed for standard deviation

class Trader:
    POSITION_LIMITS = {
        "RAINFOREST_RESIN": 50,
        "KELP": 50,
        "SQUID_INK": 50,
        "DEFAULT": 20
    }

    # EMA smoothing factor
    ALPHA = 0.3

    # --- Parameters for Dynamic Spread ---
    VOLATILITY_WINDOW = 15 # How many past prices for volatility calc
    # How much volatility increases the spread (TUNE THIS)
    VOLATILITY_SPREAD_FACTOR = 0.3

    # --- Product-specific BASE parameters ---
    # Adjusted based on historical trend observations
    PRODUCT_PARAMS = {
        # Stable: Tight base spread, higher volume
        "RAINFOREST_RESIN": { "base_spread": 1.5, "volume": 10 },
        # Volatile: Wider base spread, moderate volume
        "KELP":             { "base_spread": 2.5, "volume": 8 },
         # Volatile/Pattern?: Wider base spread, lower volume initially
        "SQUID_INK":        { "base_spread": 3.0, "volume": 6 },
        "DEFAULT":          { "base_spread": 3.0, "volume": 5 }
    }

    def get_position_limit(self, product):
        return self.POSITION_LIMITS.get(product, self.POSITION_LIMITS["DEFAULT"])

    def get_product_params(self, product):
        return self.PRODUCT_PARAMS.get(product, self.PRODUCT_PARAMS["DEFAULT"])

    def calculate_volatility(self, prices: List[float], window: int) -> float:
        """Calculates simple standard deviation as volatility."""
        if len(prices) < window:
            # Return a default low volatility if not enough data
            return 0.5
        return statistics.stdev(prices[-window:])

    def run(self, state: TradingState):
        try:
            trader_data = json.loads(state.traderData) if state.traderData else {}
        except json.JSONDecodeError:
            trader_data = {}

        # Initialize persistent data structures
        if "ema_prices" not in trader_data: trader_data["ema_prices"] = {}
        if "price_history" not in trader_data: trader_data["price_history"] = {}

        result = {}

        for product in state.order_depths:
            order_depth: OrderDepth = state.order_depths[product]
            orders: List[Order] = []

            if not order_depth.buy_orders or not order_depth.sell_orders:
                continue

            best_bid = max(order_depth.buy_orders.keys())
            best_ask = min(order_depth.sell_orders.keys())

            if best_bid >= best_ask:
                 continue

            mid_price = (best_bid + best_ask) / 2

            # Update price history
            if product not in trader_data["price_history"]:
                trader_data["price_history"][product] = []
            trader_data["price_history"][product].append(mid_price)
            trader_data["price_history"][product] = trader_data["price_history"][product][-max(50, self.VOLATILITY_WINDOW):]

            # --- EMA Calculation ---
            if product not in trader_data["ema_prices"]:
                trader_data["ema_prices"][product] = mid_price
                acceptable_price = mid_price
            else:
                old_ema = trader_data["ema_prices"][product]
                new_ema = self.ALPHA * mid_price + (1 - self.ALPHA) * old_ema
                trader_data["ema_prices"][product] = new_ema
                acceptable_price = new_ema

            # --- Market Making Logic with Dynamic Spread ---
            params = self.get_product_params(product)
            base_spread = params["base_spread"]
            trade_volume = params["volume"]

            position_limit = self.get_position_limit(product)
            current_position = state.position.get(product, 0)
            max_buy_capacity = position_limit - current_position
            max_sell_capacity = position_limit + current_position

            # 1. Calculate Volatility
            volatility = self.calculate_volatility(
                trader_data["price_history"][product],
                self.VOLATILITY_WINDOW
            )

            # 2. Calculate Dynamic Spread
            dynamic_spread = base_spread + (volatility * self.VOLATILITY_SPREAD_FACTOR)
            dynamic_spread = max(1.0, dynamic_spread) # Ensure spread is at least 1
            # Optional Cap: dynamic_spread = min(dynamic_spread, base_spread * 3)

            # 3. Calculate Buy/Sell Prices (NO inventory skew)
            # Place orders symmetrically around the acceptable price
            our_buy_price = math.floor(acceptable_price - dynamic_spread / 2)
            our_sell_price = math.ceil(acceptable_price + dynamic_spread / 2)

            # --- Place Orders ---
            final_buy_volume = min(trade_volume, max_buy_capacity)
            if final_buy_volume > 0 and our_buy_price < best_ask:
                orders.append(Order(product, our_buy_price, final_buy_volume))
                # print(f"PLACING BUY {product}: {final_buy_volume}x at {our_buy_price} (EMA:{acceptable_price:.1f}, Vol:{volatility:.1f}, Sprd:{dynamic_spread:.1f})")

            final_sell_volume = min(trade_volume, max_sell_capacity)
            if final_sell_volume > 0 and our_sell_price > best_bid:
                orders.append(Order(product, our_sell_price, -final_sell_volume))
                # print(f"PLACING SELL {product}: {final_sell_volume}x at {our_sell_price} (EMA:{acceptable_price:.1f}, Vol:{volatility:.1f}, Sprd:{dynamic_spread:.1f})")

            result[product] = orders

        # Persist necessary data
        traderData = json.dumps(trader_data, separators=(',', ':'))
        conversions = 0

        return result, conversions, traderData