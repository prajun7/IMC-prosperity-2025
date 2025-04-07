from datamodel import OrderDepth, TradingState, Order
from typing import List
import json

class Trader:
    POSITION_LIMITS = {
        "RAINFOREST_RESIN": 10,
        "KELP": 20,
    }

    def run(self, state: TradingState):
        # Load previous trader data
        trader_data = json.loads(state.traderData) if state.traderData else {}
        result = {}  # Dictionary to hold orders for each product
        conversions = 0  # Number of conversions (not implemented yet)

        # Process each product in the order book
        for product in state.order_depths:
            order_depth: OrderDepth = state.order_depths[product]
            orders: List[Order] = []

            # Skip if there are no buy or sell orders
            if not (order_depth.buy_orders and order_depth.sell_orders):
                continue

            # Calculate best bid and ask prices
            best_bid = max(order_depth.buy_orders.keys())
            best_ask = min(order_depth.sell_orders.keys())
            mid_price = (best_bid + best_ask) / 2

            # Get current position and position limit
            current_position = state.position.get(product, 0)
            position_limit = self.POSITION_LIMITS.get(product, 20)

            # Simple trading logic: buy if price is rising, sell if falling
            prev_mid_price = trader_data.get(product, {}).get("prev_mid_price", mid_price)
            if mid_price > prev_mid_price and current_position < position_limit:
                buy_amount = min(position_limit - current_position, -order_depth.sell_orders.get(best_ask, 0))
                if buy_amount > 0:
                    orders.append(Order(product, best_ask, buy_amount))
            elif mid_price < prev_mid_price and current_position > -position_limit:
                sell_amount = min(position_limit + current_position, order_depth.buy_orders.get(best_bid, 0))
                if sell_amount > 0:
                    orders.append(Order(product, best_bid, -sell_amount))

            # If there are orders, add them to the result
            if orders:
                result[product] = orders

            # Update trader data with the current mid-price
            trader_data.setdefault(product, {})["prev_mid_price"] = mid_price

        # Return all three required components
        return result, conversions, json.dumps(trader_data)