import json
from datamodel import OrderDepth, UserId, TradingState, Order
from typing import List
import string

class Trader:
    def __init__(self):
        # Initialize state to store historical trade data
        self.state = {}

    def run(self, state: TradingState):
        # Deserialize previous state from traderData
        if state.traderData:
            self.state = json.loads(state.traderData)
        else:
            self.state = {}

        print("traderData: " + state.traderData)
        print("Observations: " + str(state.observations))

        # Orders to be placed
        result = {}

        # Process each product in the order book
        for product in state.order_depths:
            order_depth: OrderDepth = state.order_depths[product]
            orders: List[Order] = []

            # Calculate mid-price from current order depth
            mid_price = self.get_mid_price(order_depth)
            if mid_price is None:
                print(f"No valid mid-price for {product}, skipping.")
                continue

            # Calculate acceptable price based on historical trades
            acceptable_price = self.calculate_acceptable_price(product, mid_price)
            if acceptable_price is None:
                acceptable_price = mid_price  # Fallback to mid-price if no historical data

            print(f"Acceptable price for {product}: {acceptable_price}")
            print(f"Buy Order depth: {len(order_depth.buy_orders)}, Sell order depth: {len(order_depth.sell_orders)}")

            # Check sell orders (buy opportunity)
            if len(order_depth.sell_orders) > 0:
                best_ask, best_ask_amount = min(order_depth.sell_orders.items())
                if best_ask < acceptable_price:
                    print(f"BUY {product}, {str(-best_ask_amount)}x {best_ask}")
                    orders.append(Order(product, best_ask, -best_ask_amount))

            # Check buy orders (sell opportunity)
            if len(order_depth.buy_orders) > 0:
                best_bid, best_bid_amount = max(order_depth.buy_orders.items())
                if best_bid > acceptable_price:
                    print(f"SELL {product}, {str(best_bid_amount)}x {best_bid}")
                    orders.append(Order(product, best_bid, -best_bid_amount))

            result[product] = orders

        # Update state with new trade data
        self.update_state(state)

        # Serialize state for next iteration
        traderData = json.dumps(self.state)
        conversions = 1  # Sample conversion request
        return result, conversions, traderData

    def get_mid_price(self, order_depth: OrderDepth) -> float:
        """Calculate the mid-price from the order depth."""
        if order_depth.buy_orders and order_depth.sell_orders:
            best_bid = max(order_depth.buy_orders.keys())
            best_ask = min(order_depth.sell_orders.keys())
            return (best_bid + best_ask) / 2
        return None

    def calculate_acceptable_price(self, product: str, current_mid_price: float) -> float:
        """Calculate acceptable price based on historical trades with counterparties."""
        total_weight = 0
        weighted_price = 0
        k = 0.5  # Profitability adjustment factor

        for counterparty in self.state:
            if product in self.state[counterparty]:
                # Use equal weights for simplicity; could use trade frequency instead
                weight = 1
                ewma_price = self.state[counterparty][product].get('price', current_mid_price)
                ewma_profit = self.state[counterparty][product].get('profit', 0)
                adjustment = k * ewma_profit
                adjusted_price = ewma_price + adjustment
                weighted_price += weight * adjusted_price
                total_weight += weight

        if total_weight > 0:
            return weighted_price / total_weight
        return None  # No historical data, return None to use mid-price as fallback

    def update_state(self, state: TradingState):
        """Update the state with new trade data using EWMA."""
        alpha = 0.1  # Smoothing factor for EWMA

        for product in state.own_trades:
            for trade in state.own_trades[product]:
                counterparty = trade.counter_party
                price = trade.price
                quantity = trade.quantity
                mid_price = self.get_mid_price(state.order_depths[product])

                if mid_price is None:
                    continue  # Skip if no valid mid-price

                # Calculate profit per unit
                if quantity > 0:  # We bought
                    profit_per_unit = mid_price - price
                else:  # We sold
                    profit_per_unit = price - mid_price

                # Initialize state for new counterparty or product
                if counterparty not in self.state:
                    self.state[counterparty] = {}
                if product not in self.state[counterparty]:
                    self.state[counterparty][product] = {'price': price, 'profit': profit_per_unit}
                else:
                    # Update EWMA for price and profit
                    old_price = self.state[counterparty][product]['price']
                    old_profit = self.state[counterparty][product]['profit']
                    new_price = alpha * price + (1 - alpha) * old_price
                    new_profit = alpha * profit_per_unit + (1 - alpha) * old_profit
                    self.state[counterparty][product]['price'] = new_price
                    self.state[counterparty][product]['profit'] = new_profit