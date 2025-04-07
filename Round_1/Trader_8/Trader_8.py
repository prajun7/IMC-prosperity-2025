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
    ALPHA_SHORT = 0.3  # Short-term EMA
    ALPHA_LONG = 0.1   # Long-term EMA

    def get_position_limit(self, product):
        """Get the position limit for a given product."""
        return self.POSITION_LIMITS.get(product, self.POSITION_LIMITS["DEFAULT"])

    def run(self, state: TradingState):
        """Execute trading logic based on trends and positions."""
        # Load trader data (EMAs)
        trader_data = json.loads(state.traderData) if state.traderData else {}
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
                continue

            mid_price = (best_bid + best_ask) / 2

            # Update EMAs
            if product not in trader_data["ema_short"]:
                trader_data["ema_short"][product] = mid_price
                trader_data["ema_long"][product] = mid_price
            else:
                trader_data["ema_short"][product] = (
                    self.ALPHA_SHORT * mid_price +
                    (1 - self.ALPHA_SHORT) * trader_data["ema_short"][product]
                )
                trader_data["ema_long"][product] = (
                    self.ALPHA_LONG * mid_price +
                    (1 - self.ALPHA_LONG) * trader_data["ema_long"][product]
                )

            short_ema = trader_data["ema_short"][product]
            long_ema = trader_data["ema_long"][product]

            # Detect trend
            trend = "up" if short_ema > long_ema else "down"

            # Set offsets based on product volatility
            if product == "SQUID_INK":
                OFFSET = 2        # Closer offset
                LARGER_OFFSET = 4 # Further offset
            else:
                OFFSET = 1
                LARGER_OFFSET = 3

            # Set buy/sell prices based on trend
            if trend == "up":
                buy_price = math.floor(short_ema - OFFSET)
                sell_price = math.ceil(short_ema + LARGER_OFFSET)
            else:
                buy_price = math.floor(short_ema - LARGER_OFFSET)
                sell_price = math.ceil(short_ema + OFFSET)

            # Calculate available capacity
            max_buy_capacity = position_limit - current_position
            max_sell_capacity = position_limit + current_position

            # Place market-making orders
            if max_buy_capacity > 0 and buy_price < best_ask:
                buy_volume = min(5, max_buy_capacity)
                orders.append(Order(product, buy_price, buy_volume))
            if max_sell_capacity > 0 and sell_price > best_bid:
                sell_volume = min(5, max_sell_capacity)
                orders.append(Order(product, sell_price, -sell_volume))

            # Unwind positions against the trend
            if trend == "down" and current_position > 0:
                unwind_sell_price = best_bid - 1
                unwind_volume = min(5, current_position)
                orders.append(Order(product, unwind_sell_price, -unwind_volume))
            if trend == "up" and current_position < 0:
                unwind_buy_price = best_ask + 1
                unwind_volume = min(5, -current_position)
                orders.append(Order(product, unwind_buy_price, unwind_volume))

            if orders:
                result[product] = orders

        # Save trader data
        traderData = json.dumps(trader_data)
        return result, 0, traderData