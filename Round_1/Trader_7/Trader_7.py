from datamodel import OrderDepth, TradingState, Order
from typing import List
import json
import math

class Trader:
    # Position limits for each product
    POSITION_LIMITS = {
        "RAINFOREST_RESIN": 50,
        "KELP": 50,
        "SQUID_INK": 50,
        "DEFAULT": 20
    }
    ALPHA_SHORT = 0.3  # Short-term EMA for quick price movements
    ALPHA_LONG = 0.1   # Long-term EMA for broader trends

    def get_position_limit(self, product):
        """Get the position limit for a given product."""
        return self.POSITION_LIMITS.get(product, self.POSITION_LIMITS["DEFAULT"])

    def run(self, state: TradingState):
        """Run the trading logic based on trends and positions."""
        # Load previous trader data (e.g., EMAs)
        try:
            trader_data = json.loads(state.traderData) if state.traderData else {}
        except json.JSONDecodeError:
            trader_data = {}

        # Initialize EMA dictionaries if they don’t exist
        if "ema_short" not in trader_data:
            trader_data["ema_short"] = {}
            trader_data["ema_long"] = {}

        result = {}  # Store orders for each product

        for product in state.order_depths:
            order_depth: OrderDepth = state.order_depths[product]
            orders: List[Order] = []
            position_limit = self.get_position_limit(product)
            current_position = state.position.get(product, 0)

            # Skip if order book is empty or invalid
            if not order_depth.buy_orders or not order_depth.sell_orders:
                continue

            best_bid = max(order_depth.buy_orders.keys())
            best_ask = min(order_depth.sell_orders.keys())
            if best_bid >= best_ask:
                continue  # Skip if book is crossed or invalid

            mid_price = (best_bid + best_ask) / 2

            # Update EMAs
            if product not in trader_data["ema_short"]:
                trader_data["ema_short"][product] = mid_price
                trader_data["ema_long"][product] = mid_price
            else:
                old_short_ema = trader_data["ema_short"][product]
                trader_data["ema_short"][product] = (self.ALPHA_SHORT * mid_price +
                                                    (1 - self.ALPHA_SHORT) * old_short_ema)
                old_long_ema = trader_data["ema_long"][product]
                trader_data["ema_long"][product] = (self.ALPHA_LONG * mid_price +
                                                   (1 - self.ALPHA_LONG) * old_long_ema)

            short_ema = trader_data["ema_short"][product]
            long_ema = trader_data["ema_long"][product]

            # Detect trend
            trend = "up" if short_ema > long_ema else "down"

            # Set offsets based on product volatility
            if product == "SQUID_INK":
                OFFSET = 2        # Closer offset for volatile product
                LARGER_OFFSET = 4 # Further offset for bigger profits
            else:
                OFFSET = 1        # Closer offset for stable products
                LARGER_OFFSET = 3 # Further offset

            # Set buy/sell prices based on trend
            if trend == "up":
                our_buy_price = math.floor(short_ema - OFFSET)
                our_sell_price = math.ceil(short_ema + LARGER_OFFSET)
            else:
                our_buy_price = math.floor(short_ema - LARGER_OFFSET)
                our_sell_price = math.ceil(short_ema + OFFSET)

            # Calculate available capacity
            max_buy_capacity = position_limit - current_position
            max_sell_capacity = position_limit + current_position

            # Place market-making orders with smaller sizes
            if max_buy_capacity > 0 and our_buy_price < best_ask:
                buy_volume = min(5, max_buy_capacity)
                orders.append(Order(product, our_buy_price, buy_volume))

            if max_sell_capacity > 0 and our_sell_price > best_bid:
                sell_volume = min(5, max_sell_capacity)
                orders.append(Order(product, our_sell_price, -sell_volume))

            # Unwind positions against the trend
            if trend == "down" and current_position > 0:
                unwind_sell_price = best_bid - 1
                unwind_sell_volume = min(5, current_position)
                if unwind_sell_volume > 0:
                    orders.append(Order(product, unwind_sell_price, -unwind_sell_volume))

            if trend == "up" and current_position < 0:
                unwind_buy_price = best_ask + 1
                unwind_buy_volume = min(5, -current_position)
                if unwind_buy_volume > 0:
                    orders.append(Order(product, unwind_buy_price, unwind_buy_volume))

            if orders:
                result[product] = orders

        # Save updated trader data
        traderData = json.dumps(trader_data, separators=(',', ':'))
        conversions = 0  # No conversions needed for this strategy
        return result, conversions, traderData