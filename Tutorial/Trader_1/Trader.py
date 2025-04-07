from datamodel import OrderDepth, TradingState, Order
from typing import List
import json

class Trader:
    # Define position limits per product; adjust based on challenge 'Rounds' data
    POSITION_LIMITS = {
        "RAINFOREST_RESIN": 10,
        "KELP": 20,
    }
    DEFAULT_LIMIT = 20  # Fallback if product not specified
    ALPHA = 1 / 3  # EMA smoothing factor, equivalent to N=5

    def run(self, state: TradingState):
        """
        Process TradingState and return orders, conversions, and updated traderData.
        
        Args:
            state: TradingState object with market data.
        
        Returns:
            tuple: (result: dict of orders, conversions: int, traderData: str)
        """
        # Load previous traderData
        trader_data = json.loads(state.traderData) if state.traderData else {}
        result = {}

        for product in state.order_depths:
            order_depth: OrderDepth = state.order_depths[product]
            orders: List[Order] = []

            # Skip if no buy or sell orders available
            if not (order_depth.buy_orders and order_depth.sell_orders):
                continue

            # Calculate mid-price
            best_bid = max(order_depth.buy_orders.keys())
            best_ask = min(order_depth.sell_orders.keys())
            mid_price = (best_bid + best_ask) / 2

            # Update EMA
            if product not in trader_data:
                trader_data[product] = {"ema": mid_price}
            else:
                old_ema = trader_data[product]["ema"]
                new_ema = self.ALPHA * mid_price + (1 - self.ALPHA) * old_ema
                trader_data[product]["ema"] = new_ema
            acceptable_price = trader_data[product]["ema"]

            # Position and limits
            position_limit = self.POSITION_LIMITS.get(product, self.DEFAULT_LIMIT)
            current_position = state.position.get(product, 0)
            max_buy = position_limit - current_position
            max_sell = position_limit + current_position

            # Trading decisions
            if mid_price < acceptable_price and max_buy > 0:
                best_ask_amount = order_depth.sell_orders[best_ask]  # Negative
                buy_amount = min(max_buy, -best_ask_amount)  # Convert to positive
                if buy_amount > 0:
                    orders.append(Order(product, best_ask, buy_amount))
                    print(f"BUY {product} {buy_amount}x at {best_ask}")

            elif mid_price > acceptable_price and max_sell > 0:
                best_bid_amount = order_depth.buy_orders[best_bid]  # Positive
                sell_amount = min(max_sell, best_bid_amount)
                if sell_amount > 0:
                    orders.append(Order(product, best_bid, -sell_amount))
                    print(f"SELL {product} {sell_amount}x at {best_bid}")

            if orders:
                result[product] = orders

        # Serialize updated traderData
        traderData = json.dumps(trader_data)
        conversions = 0  # No conversions implemented yet

        return result, conversions, traderData
