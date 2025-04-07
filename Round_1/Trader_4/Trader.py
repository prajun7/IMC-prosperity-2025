import json
from typing import List, Dict, Tuple
import numpy as np
import math # Added for isnan check if numpy isn't strictly required by platform

# Import necessary datamodel components
from datamodel import OrderDepth, TradingState, Order

# --- Constants and Parameters ---
# Rainforest Resin
RESIN_FAIR_VALUE = 10010 # Adjusted based on visual inspection (seems to oscillate around 10010-10015)
RESIN_THRESHOLD = 2     # Trade if price is +/- threshold from fair value (e.g., Buy <= 10008, Sell >= 10012) - Increased slightly

# Kelp - Switching to Bollinger Bands
KELP_BB_WINDOW = 20
KELP_BB_STD_DEV = 2.0

# Squid Ink - Using Bollinger Bands with wider bands
SQUID_INK_BB_WINDOW = 20
SQUID_INK_BB_STD_DEV = 2.5 # Widened bands slightly due to high volatility

# General
DEFAULT_POSITION_LIMIT = 20


class Trader:

    # Using class variable for position limits for easy access
    POSITION_LIMITS = {
        "RAINFOREST_RESIN": 50,
        "KELP": 50,
        "SQUID_INK": 50,
    }

    # Using instance variables to store state across run calls within a single day/round
    # These will be loaded from/saved to traderData string
    price_history = {}
    # ema_prices = {} # Keep if needed later

    def get_position_limit(self, product):
        """Gets the position limit for a given product."""
        return self.POSITION_LIMITS.get(product, DEFAULT_POSITION_LIMIT)

    def calculate_bollinger_bands(self, prices: List[float], window: int, std_dev_mult: float) -> Tuple[float, float, float]:
        """
        Calculates Bollinger Bands (SMA, Upper Band, Lower Band).
        Returns (np.nan, np.nan, np.nan) if not enough data.
        """
        if len(prices) < window:
            return np.nan, np.nan, np.nan # Not enough data

        # Use only the last 'window' prices
        relevant_prices = np.array(prices[-window:])
        sma = np.mean(relevant_prices)
        std_dev = np.std(relevant_prices)

        # Handle case where std_dev is zero or very close to zero
        if std_dev < 1e-6:
             return sma, sma, sma # Avoid division by zero or extreme bands if price is flat

        upper_band = sma + std_dev_mult * std_dev
        lower_band = sma - std_dev_mult * std_dev
        return sma, upper_band, lower_band

    def update_price_history(self, product: str, price: float, max_len: int):
        """Appends price to history and trims the list if it exceeds max_len."""
        if product not in self.price_history:
            self.price_history[product] = []

        history = self.price_history[product]
        history.append(price)

        # Trim efficiently if too long
        if len(history) > max_len:
            # Keep only the most recent 'max_len' entries
            self.price_history[product] = history[-max_len:]


    def run(self, state: TradingState) -> Tuple[Dict[str, List[Order]], int, str]:
        """
        Processes TradingState, executes strategies, and returns orders and updated state.
        """
        # --- State Loading ---
        try:
            # Load the dictionary from the JSON string
            trader_data_dict = json.loads(state.traderData) if state.traderData else {}
        except json.JSONDecodeError:
            # print("Error decoding traderData, starting fresh.") # Reduce noise
            trader_data_dict = {}

        # Load price history from the dictionary into the instance variable
        # Use .get() to handle cases where the key might not exist yet
        self.price_history = trader_data_dict.get("price_history", {})
        # self.ema_prices = trader_data_dict.get("ema_prices", {}) # If using EMA

        result_orders: Dict[str, List[Order]] = {} # Orders to be placed this timestamp

        # --- Strategy Execution Loop ---
        for product in state.order_depths:
            # Basic checks for data validity
            if product not in state.order_depths:
                # print(f"Warning: No order depth data for {product} in state.")
                continue # Should not happen if iterating state.order_depths keys

            order_depth = state.order_depths[product]
            if not order_depth or not order_depth.buy_orders or not order_depth.sell_orders:
                # print(f"Warning: Empty order book for {product}") # Reduce noise
                continue # Skip if no liquidity

            # --- Market Data Calculation ---
            orders: List[Order] = [] # Orders for the current product
            position_limit = self.get_position_limit(product)
            current_position = state.position.get(product, 0)

            best_bid = max(order_depth.buy_orders.keys())
            best_ask = min(order_depth.sell_orders.keys())
            mid_price = (best_bid + best_ask) / 2.0

            # --- Product-Specific Strategies ---

            # 1. Rainforest Resin: Mean Reversion
            if product == "RAINFOREST_RESIN":
                buy_threshold = RESIN_FAIR_VALUE - RESIN_THRESHOLD
                sell_threshold = RESIN_FAIR_VALUE + RESIN_THRESHOLD

                # Buy Logic: If best ask is below or at the buy threshold
                if best_ask <= buy_threshold:
                    max_buy_capacity = position_limit - current_position
                    if max_buy_capacity > 0:
                        # Get volume available at best ask, default to 0 if price level disappears
                        available_volume = abs(order_depth.sell_orders.get(best_ask, 0))
                        place_volume = min(max_buy_capacity, available_volume)
                        if place_volume > 0:
                            orders.append(Order(product, best_ask, place_volume))
                            # print(f"BUY {product}: {place_volume}x at {best_ask} (<= {buy_threshold})")

                # Sell Logic: If best bid is above or at the sell threshold
                elif best_bid >= sell_threshold:
                    max_sell_capacity = position_limit + current_position # Max units we can sell (positive)
                    if max_sell_capacity > 0:
                         # Get volume available at best bid, default to 0
                        available_volume = order_depth.buy_orders.get(best_bid, 0)
                        place_volume = min(max_sell_capacity, available_volume)
                        if place_volume > 0:
                            orders.append(Order(product, best_bid, -place_volume)) # Sell order quantity is negative
                            # print(f"SELL {product}: {place_volume}x at {best_bid} (>= {sell_threshold})")

            # 2. Kelp: Bollinger Bands
            elif product == "KELP":
                window = KELP_BB_WINDOW
                std_dev_mult = KELP_BB_STD_DEV
                # Keep slightly more history than needed for calculation buffer
                max_hist_len = window + 5

                # Update history (using instance variable self.price_history)
                self.update_price_history(product, mid_price, max_hist_len)

                # Calculate Bands using the history stored in the instance
                # Ensure the product key exists before accessing
                current_product_history = self.price_history.get(product, [])
                sma, upper_band, lower_band = self.calculate_bollinger_bands(
                    current_product_history, window, std_dev_mult
                )

                # Check if bands are valid (not NaN)
                # Use math.isnan if numpy isn't guaranteed, otherwise np.isnan is fine
                if not math.isnan(sma):
                    # Buy Logic: Buy if best ask is below lower band
                    if best_ask < lower_band:
                        max_buy_capacity = position_limit - current_position
                        if max_buy_capacity > 0:
                            available_volume = abs(order_depth.sell_orders.get(best_ask, 0))
                            place_volume = min(max_buy_capacity, available_volume)
                            if place_volume > 0:
                                orders.append(Order(product, best_ask, place_volume))
                                # print(f"BUY {product}: {place_volume}x at {best_ask} (Ask {best_ask:.2f} < BB Lower {lower_band:.2f})")

                    # Sell Logic: Sell if best bid is above upper band
                    elif best_bid > upper_band:
                        max_sell_capacity = position_limit + current_position
                        if max_sell_capacity > 0:
                            available_volume = order_depth.buy_orders.get(best_bid, 0)
                            place_volume = min(max_sell_capacity, available_volume)
                            if place_volume > 0:
                                orders.append(Order(product, best_bid, -place_volume))
                                # print(f"SELL {product}: {place_volume}x at {best_bid} (Bid {best_bid:.2f} > BB Upper {upper_band:.2f})")

            # 3. Squid Ink: Bollinger Bands (wider)
            elif product == "SQUID_INK":
                window = SQUID_INK_BB_WINDOW
                std_dev_mult = SQUID_INK_BB_STD_DEV
                max_hist_len = window + 5

                # Update history
                self.update_price_history(product, mid_price, max_hist_len)

                # Calculate Bands
                current_product_history = self.price_history.get(product, [])
                sma, upper_band, lower_band = self.calculate_bollinger_bands(
                    current_product_history, window, std_dev_mult
                )

                if not math.isnan(sma): # Check if bands are valid
                     # Buy Logic: Buy if best ask is below lower band
                    if best_ask < lower_band:
                        max_buy_capacity = position_limit - current_position
                        if max_buy_capacity > 0:
                            available_volume = abs(order_depth.sell_orders.get(best_ask, 0))
                            # Aggressively fill capacity or available volume, whichever is smaller
                            place_volume = min(max_buy_capacity, available_volume)
                            if place_volume > 0:
                                orders.append(Order(product, best_ask, place_volume))
                                # print(f"BUY {product}: {place_volume}x at {best_ask} (Ask {best_ask:.2f} < BB Lower {lower_band:.2f})")

                    # Sell Logic: Sell if best bid is above upper band
                    elif best_bid > upper_band:
                        max_sell_capacity = position_limit + current_position
                        if max_sell_capacity > 0:
                            available_volume = order_depth.buy_orders.get(best_bid, 0)
                             # Aggressively fill capacity or available volume
                            place_volume = min(max_sell_capacity, available_volume)
                            if place_volume > 0:
                                orders.append(Order(product, best_bid, -place_volume))
                                # print(f"SELL {product}: {place_volume}x at {best_bid} (Bid {best_bid:.2f} > BB Upper {upper_band:.2f})")

            # Add generated orders for the current product to the results dictionary
            if orders:
                result_orders[product] = orders

        # --- State Saving ---
        # Store the updated instance variables back into the dictionary
        trader_data_dict["price_history"] = self.price_history
        # trader_data_dict["ema_prices"] = self.ema_prices # If using EMA

        # Serialize the dictionary back to a JSON string for storage
        traderData_str = json.dumps(trader_data_dict, separators=(',', ':'))

        # No conversions implemented in this round
        conversions = 0

        # Return the orders, conversions, and the serialized state
        return result_orders, conversions, traderData_str