from datamodel import OrderDepth, TradingState, Order
from typing import List
import json
import math # Need for floor and ceil

class Trader:
    POSITION_LIMITS = {
        "RAINFOREST_RESIN": 50,
        "KELP": 50,
        "SQUID_INK": 50,
        "DEFAULT": 20 # Default limit remains, though all Round 1 products are specified
    }
    ALPHA = 0.3 # EMA smoothing factor - let's keep it moderate for now

    def get_position_limit(self, product):
        """Gets the position limit for a given product."""
        return self.POSITION_LIMITS.get(product, self.POSITION_LIMITS["DEFAULT"])

    def run(self, state: TradingState):
        """
        Process TradingState trying a market making approach.
        """
        try:
            trader_data = json.loads(state.traderData) if state.traderData else {}
        except json.JSONDecodeError:
            trader_data = {}

        result = {}

        if "ema_prices" not in trader_data:
            trader_data["ema_prices"] = {}

        for product in state.order_depths:
            order_depth: OrderDepth = state.order_depths[product]
            orders: List[Order] = []
            position_limit = self.get_position_limit(product)
            current_position = state.position.get(product, 0)

            if not order_depth.buy_orders or not order_depth.sell_orders:
                continue

            best_bid = max(order_depth.buy_orders.keys())
            best_ask = min(order_depth.sell_orders.keys())

            if best_bid >= best_ask:
                 continue # Skip if book is crossed or invalid

            mid_price = (best_bid + best_ask) / 2

            # --- EMA Calculation (Same as before) ---
            if product not in trader_data["ema_prices"]:
                trader_data["ema_prices"][product] = mid_price
                acceptable_price = mid_price
            else:
                old_ema = trader_data["ema_prices"][product]
                new_ema = self.ALPHA * mid_price + (1 - self.ALPHA) * old_ema
                trader_data["ema_prices"][product] = new_ema
                acceptable_price = new_ema

            # --- Market Making Logic ---
            max_buy_capacity = position_limit - current_position
            max_sell_capacity = position_limit + current_position

            # Define our target buy/sell prices based on EMA
            # Use floor/ceil to ensure integer prices if needed by exchange
            our_buy_price = math.floor(acceptable_price - 1) # Example: Bid slightly below EMA
            our_sell_price = math.ceil(acceptable_price + 1) # Example: Ask slightly above EMA

            # --- Place BUY order ---
            # Place buy if we have capacity AND our price is better than the best ask
            # (i.e., our buy price is lower than what sellers are currently asking)
            if max_buy_capacity > 0 and our_buy_price < best_ask:
                # How much to buy? Let's try to fill our capacity for simplicity
                # You could also use a smaller fixed size, e.g., min(max_buy_capacity, 5)
                buy_volume = max_buy_capacity
                orders.append(Order(product, our_buy_price, buy_volume))
                # print(f"PLACING BUY {product}: {buy_volume}x at {our_buy_price} (EMA: {acceptable_price:.2f})")


            # --- Place SELL order ---
            # Place sell if we have capacity AND our price is better than the best bid
            # (i.e., our sell price is higher than what buyers are currently offering)
            if max_sell_capacity > 0 and our_sell_price > best_bid:
                # How much to sell? Let's try to fill our capacity (need negative sign)
                # You could use a smaller fixed size, e.g., min(max_sell_capacity, 5)
                sell_volume = max_sell_capacity # This is positive capacity
                orders.append(Order(product, our_sell_price, -sell_volume)) # Quantity must be negative
                # print(f"PLACING SELL {product}: {sell_volume}x at {our_sell_price} (EMA: {acceptable_price:.2f})")


            if orders:
                result[product] = orders

        traderData = json.dumps(trader_data, separators=(',', ':'))
        conversions = 0

        return result, conversions, traderData