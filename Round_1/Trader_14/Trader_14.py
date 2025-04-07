from datamodel import OrderDepth, TradingState, Order
from typing import List, Dict
import json
import math

class Trader:
    # Position limits remain crucial
    POSITION_LIMITS = {
        "RAINFOREST_RESIN": 50,
        "KELP": 50,
        "SQUID_INK": 50,
        "DEFAULT": 20
    }

    # --- Simplified Parameters ---
    # Fixed EMA smoothing factor
    ALPHA = 0.3

    # Simple product-specific parameters: spread around EMA & fixed trade volume
    # Adjust these based on testing!
    # Wider spread for more volatile products? Larger volume for stable?
    PRODUCT_PARAMS = {
        "RAINFOREST_RESIN": { "spread": 2, "volume": 10 }, # Stable product, maybe tighter spread/higher vol?
        "KELP":             { "spread": 3, "volume": 8 },  # Up/Down, wider spread?
        "SQUID_INK":        { "spread": 4, "volume": 6 },  # Swings/Pattern, wider spread, lower vol?
        "DEFAULT":          { "spread": 3, "volume": 5 }   # Default for safety
    }

    def get_position_limit(self, product):
        """Gets the position limit for a given product."""
        return self.POSITION_LIMITS.get(product, self.POSITION_LIMITS["DEFAULT"])

    def get_product_params(self, product):
        """Gets the simplified trading parameters for a given product."""
        return self.PRODUCT_PARAMS.get(product, self.PRODUCT_PARAMS["DEFAULT"])

    def run(self, state: TradingState):
        """
        Simplified market making strategy based on EMA.
        """
        # Load/Initialize traderData for EMA prices
        try:
            trader_data = json.loads(state.traderData) if state.traderData else {}
        except json.JSONDecodeError:
            trader_data = {}

        if "ema_prices" not in trader_data:
            trader_data["ema_prices"] = {}

        result = {} # Orders to be placed

        for product in state.order_depths:
            order_depth: OrderDepth = state.order_depths[product]
            orders: List[Order] = []

            # Get basic market state
            if not order_depth.buy_orders or not order_depth.sell_orders:
                continue # Need both sides for price calculation

            best_bid = max(order_depth.buy_orders.keys())
            best_ask = min(order_depth.sell_orders.keys())

            if best_bid >= best_ask:
                 continue # Skip if book is crossed or invalid

            mid_price = (best_bid + best_ask) / 2

            # --- EMA Calculation ---
            if product not in trader_data["ema_prices"]:
                trader_data["ema_prices"][product] = mid_price
                acceptable_price = mid_price
            else:
                old_ema = trader_data["ema_prices"][product]
                new_ema = self.ALPHA * mid_price + (1 - self.ALPHA) * old_ema
                trader_data["ema_prices"][product] = new_ema
                acceptable_price = new_ema

            # --- Simple Market Making Logic ---
            params = self.get_product_params(product)
            spread = params["spread"]
            trade_volume = params["volume"]

            position_limit = self.get_position_limit(product)
            current_position = state.position.get(product, 0)
            max_buy_capacity = position_limit - current_position
            max_sell_capacity = position_limit + current_position

            # Define our target buy/sell prices based on EMA and fixed spread
            our_buy_price = math.floor(acceptable_price - spread)
            our_sell_price = math.ceil(acceptable_price + spread)

            # --- Place BUY order ---
            # Calculate volume, respecting capacity and fixed trade size
            final_buy_volume = min(trade_volume, max_buy_capacity)
            # Place order only if we have capacity and price is passive (below best ask)
            if final_buy_volume > 0 and our_buy_price < best_ask:
                orders.append(Order(product, our_buy_price, final_buy_volume))
                # print(f"PLACING BUY {product}: {final_buy_volume}x at {our_buy_price}")

            # --- Place SELL order ---
            # Calculate volume, respecting capacity and fixed trade size
            final_sell_volume = min(trade_volume, max_sell_capacity)
            # Place order only if we have capacity and price is passive (above best bid)
            if final_sell_volume > 0 and our_sell_price > best_bid:
                orders.append(Order(product, our_sell_price, -final_sell_volume)) # Negative volume for sell
                # print(f"PLACING SELL {product}: {final_sell_volume}x at {our_sell_price}")


            result[product] = orders

        # Persist EMA prices
        traderData = json.dumps(trader_data, separators=(',', ':'))
        conversions = 0

        return result, conversions, traderData