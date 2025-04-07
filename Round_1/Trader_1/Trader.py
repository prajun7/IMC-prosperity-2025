from datamodel import OrderDepth, TradingState, Order
from typing import List
import json

class Trader:
    # Define position limits per product; adjust based on challenge 'Rounds' data
    POSITION_LIMITS = {
        "RAINFOREST_RESIN": 50,
        "KELP": 50,
        "SQUID_INK": 50,
        # Need to add other products from the challenge rounds here
        "DEFAULT": 20 # Use a default for any unspecified products
    }
    # Using a dictionary for EMA state is better if traderData is used for more later
    # ALPHA = 1 / 3  # EMA smoothing factor (N=5), maybe make it configurable or adaptive?
    ALPHA = 0.3 # smoothing factor

    def get_position_limit(self, product):
        """Gets the position limit for a given product."""
        return self.POSITION_LIMITS.get(product, self.POSITION_LIMITS["DEFAULT"])

    def run(self, state: TradingState):
        """
        Process TradingState and return orders, conversions, and updated traderData.
        """
        # Load previous traderData or initialize if empty
        try:
            # Use a default value for json.loads if traderData is empty or malformed
            trader_data = json.loads(state.traderData) if state.traderData else {}
        except json.JSONDecodeError:
            trader_data = {} # Start fresh if traderData is corrupted

        result = {} # Orders to be placed for all products

        # Initialize EMA data structure if not present
        if "ema_prices" not in trader_data:
            trader_data["ema_prices"] = {}

        for product in state.order_depths:
            order_depth: OrderDepth = state.order_depths[product]
            orders: List[Order] = []
            position_limit = self.get_position_limit(product)
            current_position = state.position.get(product, 0)

            # Ensure there are both buy and sell orders to calculate mid-price and EMA
            if not order_depth.buy_orders or not order_depth.sell_orders:
                # No liquidity or crossed book? Skip trading this product this iteration.
                continue

            # Get best bid and ask
            best_bid = max(order_depth.buy_orders.keys())
            best_ask = min(order_depth.sell_orders.keys())

            # Calculate mid-price
            mid_price = (best_bid + best_ask) / 2

            # --- EMA Calculation ---
            # Initialize EMA for the product if it's the first time seeing it
            if product not in trader_data["ema_prices"]:
                trader_data["ema_prices"][product] = mid_price
                acceptable_price = mid_price # Use mid_price for the first iteration
            else:
                old_ema = trader_data["ema_prices"][product]
                new_ema = self.ALPHA * mid_price + (1 - self.ALPHA) * old_ema
                trader_data["ema_prices"][product] = new_ema
                acceptable_price = new_ema # Use updated EMA

            # --- Trading Logic ---
            # Calculate available capacity respecting position limits
            max_buy_capacity = position_limit - current_position
            max_sell_capacity = position_limit + current_position # Max quantity we can sell (is positive)

            # --- Revised Buy Logic ---
            # If our fair value estimate (EMA) is above the best ask, consider buying
            if acceptable_price > best_ask and max_buy_capacity > 0:
                # Amount available at best ask (is negative, make it positive)
                available_ask_volume = abs(order_depth.sell_orders[best_ask])
                # Buy the minimum of available volume and our capacity
                buy_volume = min(available_ask_volume, max_buy_capacity)
                if buy_volume > 0:
                    orders.append(Order(product, best_ask, buy_volume))
                    print(f"BUY {product}: {buy_volume}x at {best_ask} (EMA: {acceptable_price:.2f})")

            # --- Revised Sell Logic ---
            # If our fair value estimate (EMA) is below the best bid, consider selling
            elif acceptable_price < best_bid and max_sell_capacity > 0:
                 # Amount available at best bid (is positive)
                available_bid_volume = order_depth.buy_orders[best_bid]
                # Sell the minimum of available volume and our capacity
                sell_volume = min(available_bid_volume, max_sell_capacity)
                if sell_volume > 0:
                     # Remember: Order quantity for SELL must be negative
                    orders.append(Order(product, best_bid, -sell_volume))
                    print(f"SELL {product}: {sell_volume}x at {best_bid} (EMA: {acceptable_price:.2f})")

            # Add orders for this product to the result dictionary
            if orders:
                result[product] = orders

        # Serialize updated traderData for the next iteration
        # Use separators for more compact JSON
        traderData = json.dumps(trader_data, separators=(',', ':'))
        conversions = 0  # No conversions implemented yet

        return result, conversions, traderData