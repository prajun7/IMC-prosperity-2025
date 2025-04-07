import json
from typing import List, Dict, Tuple
import numpy as np # For standard deviation
from datamodel import OrderDepth, TradingState, Order

# Consider making these constants or configurable
RAINFOREST_MEAN = 10000 # Initial guess, let's refine this based on data later if needed. Let's start with a simpler threshold logic.
KELP_EMA_ALPHA = 0.4 # Slightly faster EMA for Kelp
SQUID_INK_BB_WINDOW = 20 # Bollinger Band window size
SQUID_INK_BB_STD_DEV = 2 # Bollinger Band standard deviation multiplier

class Trader:
    POSITION_LIMITS = {
        "RAINFOREST_RESIN": 50,
        "KELP": 50,
        "SQUID_INK": 50,
        "DEFAULT": 20
    }

    def get_position_limit(self, product):
        return self.POSITION_LIMITS.get(product, self.POSITION_LIMITS["DEFAULT"])

    def calculate_next_ema(self, current_price: float, previous_ema: float, alpha: float) -> float:
        """Calculates the next EMA value."""
        return alpha * current_price + (1 - alpha) * previous_ema

    def calculate_bollinger_bands(self, prices: List[float], window: int, std_dev_mult: float) -> Tuple[float, float, float]:
        """Calculates Bollinger Bands (SMA, Upper Band, Lower Band)."""
        if len(prices) < window:
            return np.nan, np.nan, np.nan # Not enough data

        # Use only the last 'window' prices
        relevant_prices = prices[-window:]
        sma = np.mean(relevant_prices)
        std_dev = np.std(relevant_prices)
        upper_band = sma + std_dev_mult * std_dev
        lower_band = sma - std_dev_mult * std_dev
        return sma, upper_band, lower_band

    def run(self, state: TradingState) -> Tuple[Dict[str, List[Order]], int, str]:
        """
        Process TradingState and return orders, conversions, and updated traderData.
        """
        try:
            trader_data = json.loads(state.traderData) if state.traderData else {}
        except json.JSONDecodeError:
            print("Error decoding traderData, starting fresh.")
            trader_data = {}

        # Initialize state if not present
        if "ema_prices" not in trader_data:
            trader_data["ema_prices"] = {} # For Kelp
        if "price_history" not in trader_data:
             trader_data["price_history"] = {} # For Bollinger Bands (Squid Ink)

        result = {} # Orders to be placed for all products

        for product in state.order_depths:
            order_depth: OrderDepth = state.order_depths[product]
            orders: List[Order] = []
            position_limit = self.get_position_limit(product)
            current_position = state.position.get(product, 0)

            if not order_depth.buy_orders or not order_depth.sell_orders:
                continue # Skip if no liquidity

            best_bid = max(order_depth.buy_orders.keys())
            best_ask = min(order_depth.sell_orders.keys())
            mid_price = (best_bid + best_ask) / 2

            # --- Product-Specific Logic ---

            if product == "RAINFOREST_RESIN":
                # Strategy: Mean Reversion around a fixed price (e.g., 10000)
                # More robust: Estimate mean dynamically or use hardcoded based on observation
                # Simple Threshold Logic for now:
                fair_value = 10000 # Assume stable around this known value
                buy_threshold = 9999 # Buy if best ask is below this
                sell_threshold = 10001 # Sell if best bid is above this

                # Buy Logic
                if best_ask <= buy_threshold:
                     max_buy_capacity = position_limit - current_position
                     if max_buy_capacity > 0:
                        available_ask_volume = abs(order_depth.sell_orders[best_ask])
                        buy_volume = min(available_ask_volume, max_buy_capacity)
                        if buy_volume > 0:
                            orders.append(Order(product, best_ask, buy_volume))
                            print(f"BUY {product}: {buy_volume}x at {best_ask} (Below threshold {buy_threshold})")

                # Sell Logic
                elif best_bid >= sell_threshold:
                    max_sell_capacity = position_limit + current_position # Available units to sell
                    if max_sell_capacity > 0:
                        available_bid_volume = order_depth.buy_orders[best_bid]
                        sell_volume = min(available_bid_volume, max_sell_capacity)
                        if sell_volume > 0:
                            orders.append(Order(product, best_bid, -sell_volume))
                            print(f"SELL {product}: {sell_volume}x at {best_bid} (Above threshold {sell_threshold})")

            elif product == "KELP":
                # Strategy: EMA-based Trend Following
                if product not in trader_data["ema_prices"]:
                    trader_data["ema_prices"][product] = mid_price
                    acceptable_price = mid_price
                else:
                    old_ema = trader_data["ema_prices"][product]
                    new_ema = self.calculate_next_ema(mid_price, old_ema, KELP_EMA_ALPHA)
                    trader_data["ema_prices"][product] = new_ema
                    acceptable_price = new_ema

                # Add a small buffer to overcome spread/noise
                entry_buffer = 0.5 # Adjust as needed

                # Buy Logic
                if acceptable_price > best_ask + entry_buffer:
                    max_buy_capacity = position_limit - current_position
                    if max_buy_capacity > 0:
                        available_ask_volume = abs(order_depth.sell_orders[best_ask])
                        buy_volume = min(available_ask_volume, max_buy_capacity)
                        if buy_volume > 0:
                            orders.append(Order(product, best_ask, buy_volume))
                            print(f"BUY {product}: {buy_volume}x at {best_ask} (EMA: {acceptable_price:.2f} > Ask + Buffer)")

                # Sell Logic
                elif acceptable_price < best_bid - entry_buffer:
                     max_sell_capacity = position_limit + current_position
                     if max_sell_capacity > 0:
                        available_bid_volume = order_depth.buy_orders[best_bid]
                        sell_volume = min(available_bid_volume, max_sell_capacity)
                        if sell_volume > 0:
                            orders.append(Order(product, best_bid, -sell_volume))
                            print(f"SELL {product}: {sell_volume}x at {best_bid} (EMA: {acceptable_price:.2f} < Bid - Buffer)")


            elif product == "SQUID_INK":
                # Strategy: Bollinger Bands
                # Update price history
                if product not in trader_data["price_history"]:
                     trader_data["price_history"][product] = []
                # Keep history length manageable, e.g., window size + buffer
                trader_data["price_history"][product].append(mid_price)
                if len(trader_data["price_history"][product]) > SQUID_INK_BB_WINDOW * 2:
                     trader_data["price_history"][product].pop(0) # Remove oldest price

                # Calculate Bollinger Bands
                prices = trader_data["price_history"][product]
                sma, upper_band, lower_band = self.calculate_bollinger_bands(
                    prices, SQUID_INK_BB_WINDOW, SQUID_INK_BB_STD_DEV
                )

                if not np.isnan(sma): # Check if bands are valid
                    # Buy Logic: Buy if price touches or crosses below lower band
                    if mid_price < lower_band: # or best_ask < lower_band
                        max_buy_capacity = position_limit - current_position
                        if max_buy_capacity > 0:
                            # Take available liquidity at best ask
                            available_ask_volume = abs(order_depth.sell_orders[best_ask])
                            buy_volume = min(available_ask_volume, max_buy_capacity)
                            # Optional: Scale trade size based on how far below the band? Start simple.
                            if buy_volume > 0:
                                orders.append(Order(product, best_ask, buy_volume))
                                print(f"BUY {product}: {buy_volume}x at {best_ask} (MidPrice {mid_price:.2f} < BB Lower {lower_band:.2f})")

                    # Sell Logic: Sell if price touches or crosses above upper band
                    elif mid_price > upper_band: # or best_bid > upper_band
                        max_sell_capacity = position_limit + current_position
                        if max_sell_capacity > 0:
                             # Take available liquidity at best bid
                            available_bid_volume = order_depth.buy_orders[best_bid]
                            sell_volume = min(available_bid_volume, max_sell_capacity)
                            # Optional: Scale trade size? Start simple.
                            if sell_volume > 0:
                                orders.append(Order(product, best_bid, -sell_volume))
                                print(f"SELL {product}: {sell_volume}x at {best_bid} (MidPrice {mid_price:.2f} > BB Upper {upper_band:.2f})")
                    # Optional: Add logic to close positions when price reverts towards SMA?

            # Add orders for this product to the result dictionary
            if orders:
                result[product] = orders

        # Serialize updated traderData
        traderData = json.dumps(trader_data, separators=(',', ':'))
        conversions = 0 # No conversions implemented yet

        return result, conversions, traderData