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

    # Parameters for new logic
    # How many past prices to use for volatility calculation
    VOLATILITY_WINDOW = 15
    # How much volatility increases the spread (tune this)
    VOLATILITY_SPREAD_FACTOR = 0.3
    # How much our position skews the price (tune this)
    POSITION_SKEW_FACTOR = 0.04 # Scaled by position ratio


    # Product-specific BASE parameters (spread will be dynamic)
    # Might need tuning, especially base_spread
    PRODUCT_PARAMS = {
        "RAINFOREST_RESIN": { "base_spread": 1.5, "volume": 10 }, # Stable, tighter base spread
        "KELP":             { "base_spread": 2.5, "volume": 8 },
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
            return 0.0 # Not enough data
        # Use the prices directly for standard deviation calculation
        return statistics.stdev(prices[-window:])

    def run(self, state: TradingState):
        try:
            trader_data = json.loads(state.traderData) if state.traderData else {}
        except json.JSONDecodeError:
            trader_data = {}

        # Initialize persistent data structures if they don't exist
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

            # Update price history (used for volatility)
            if product not in trader_data["price_history"]:
                trader_data["price_history"][product] = []
            trader_data["price_history"][product].append(mid_price)
            # Keep history length manageable
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

            # --- Improved Market Making Logic ---
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
            # Increase spread proportional to volatility
            dynamic_spread = base_spread + (volatility * self.VOLATILITY_SPREAD_FACTOR)
            # Ensure spread is reasonable (e.g., at least 1, maybe cap max?)
            dynamic_spread = max(1.0, dynamic_spread)
            # Optional: Cap max spread if needed: dynamic_spread = min(dynamic_spread, base_spread * 3)

            # 3. Calculate Inventory Skew
            # Skew price levels based on current position ratio
            position_ratio = current_position / position_limit if position_limit != 0 else 0
            # Price adjustment based on skew - scaled by volatility maybe? No, keep simple first.
            price_skew = (position_ratio * dynamic_spread * self.POSITION_SKEW_FACTOR) # Skew proportional to spread makes sense

            # 4. Calculate Adjusted Buy/Sell Prices
            # Base prices around EMA using dynamic spread
            base_buy_price = acceptable_price - (dynamic_spread / 2)
            base_sell_price = acceptable_price + (dynamic_spread / 2)

            # Apply skew: If long (ratio>0), skew<0; If short (ratio<0), skew>0 (Error in previous thinking, need to adjust based on ratio SIGN)
            # Let's rethink skew: If long (pos>0), we want to buy lower and sell lower (easier to sell). If short (pos<0), buy higher and sell higher.
            # Skew factor should perhaps scale the EMA adjustment away from midprice
            # Simpler: Shift midpoint based on skew.
            adjusted_midpoint = acceptable_price - price_skew # If long, midpoint shifts down. If short, shifts up.

            our_buy_price = math.floor(adjusted_midpoint - dynamic_spread / 2)
            our_sell_price = math.ceil(adjusted_midpoint + dynamic_spread / 2)


            # --- Place Orders ---
            # Calculate volume, respecting capacity and fixed trade size
            final_buy_volume = min(trade_volume, max_buy_capacity)
            if final_buy_volume > 0 and our_buy_price < best_ask:
                orders.append(Order(product, our_buy_price, final_buy_volume))
                # print(f"PLACING BUY {product}: {final_buy_volume}x at {our_buy_price} (EMA:{acceptable_price:.1f}, Vol:{volatility:.1f}, Sprd:{dynamic_spread:.1f}, Skw:{price_skew:.1f})")


            final_sell_volume = min(trade_volume, max_sell_capacity)
            if final_sell_volume > 0 and our_sell_price > best_bid:
                orders.append(Order(product, our_sell_price, -final_sell_volume)) # Negative volume for sell
                # print(f"PLACING SELL {product}: {final_sell_volume}x at {our_sell_price} (EMA:{acceptable_price:.1f}, Vol:{volatility:.1f}, Sprd:{dynamic_spread:.1f}, Skw:{price_skew:.1f})")


            result[product] = orders

        # Persist necessary data
        traderData = json.dumps(trader_data, separators=(',', ':'))
        conversions = 0

        return result, conversions, traderData