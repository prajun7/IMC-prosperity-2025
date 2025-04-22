from typing import Dict, List
from datamodel import Order, OrderDepth, TradingState

class Trader:
    def __init__(self):
        self.position_limits = {
            "PICNIC_BASKET1": 60,
            "PICNIC_BASKET2": 100,
            "CROISSANTS": 250,
            "JAMS": 350,
            "DJEMBES": 60
        }
        self.profit_buffer = 3  # Reduced from 5
        self.basket1_composition = {"CROISSANTS": 6, "JAMS": 3, "DJEMBES": 1}
        self.basket2_composition = {"CROISSANTS": 4, "JAMS": 2}

    def get_mid(self, product: str, state: TradingState) -> float:
        if product not in state.order_depths:
            return None
        bids = state.order_depths[product].buy_orders
        asks = state.order_depths[product].sell_orders
        if bids and asks:
            return (max(bids.keys()) + min(asks.keys())) / 2
        return None

    def within_limits(self, state: TradingState, product: str, qty: int) -> bool:
        current_position = state.position.get(product, 0)
        new_position = current_position + qty
        return abs(new_position) <= self.position_limits[product]

    def run(self, state: TradingState) -> tuple[Dict[str, List[Order]], int, str]:
        orders: Dict[str, List[Order]] = {}

        # Get mid prices
        croissant_mid = self.get_mid("CROISSANTS", state)
        jam_mid = self.get_mid("JAMS", state)
        djembe_mid = self.get_mid("DJEMBES", state)
        basket1_mid = self.get_mid("PICNIC_BASKET1", state)
        basket2_mid = self.get_mid("PICNIC_BASKET2", state)

        # PICNIC_BASKET1 Arbitrage
        if all([croissant_mid, jam_mid, djembe_mid, basket1_mid]):
            basket1_value = (self.basket1_composition["CROISSANTS"] * croissant_mid +
                             self.basket1_composition["JAMS"] * jam_mid +
                             self.basket1_composition["DJEMBES"] * djembe_mid)

            if basket1_mid > basket1_value + self.profit_buffer:
                # Basket overpriced: Sell basket, buy components
                if self.within_limits(state, "PICNIC_BASKET1", -1):
                    best_bid = max(state.order_depths["PICNIC_BASKET1"].buy_orders.keys())
                    volume = min(state.order_depths["PICNIC_BASKET1"].buy_orders[best_bid], 
                               self.position_limits["PICNIC_BASKET1"] - abs(state.position.get("PICNIC_BASKET1", 0)))
                    if volume > 0:
                        orders["PICNIC_BASKET1"] = [Order("PICNIC_BASKET1", best_bid, -volume)]
                        # Buy components
                        for product, qty in self.basket1_composition.items():
                            if self.within_limits(state, product, volume * qty):
                                best_ask = min(state.order_depths[product].sell_orders.keys())
                                avail_volume = min(state.order_depths[product].sell_orders[best_ask], volume * qty)
                                if avail_volume > 0:
                                    orders[product] = orders.get(product, []) + [Order(product, best_ask, avail_volume)]

            elif basket1_mid < basket1_value - self.profit_buffer:
                # Basket underpriced: Buy basket, sell components
                if self.within_limits(state, "PICNIC_BASKET1", 1):
                    best_ask = min(state.order_depths["PICNIC_BASKET1"].sell_orders.keys())
                    volume = min(state.order_depths["PICNIC_BASKET1"].sell_orders[best_ask],
                               self.position_limits["PICNIC_BASKET1"] - abs(state.position.get("PICNIC_BASKET1", 0)))
                    if volume > 0:
                        orders["PICNIC_BASKET1"] = [Order("PICNIC_BASKET1", best_ask, volume)]
                        # Sell components
                        for product, qty in self.basket1_composition.items():
                            if self.within_limits(state, product, -volume * qty):
                                best_bid = max(state.order_depths[product].buy_orders.keys())
                                avail_volume = min(state.order_depths[product].buy_orders[best_bid], volume * qty)
                                if avail_volume > 0:
                                    orders[product] = orders.get(product, []) + [Order(product, best_bid, -avail_volume)]

        # PICNIC_BASKET2 Arbitrage
        if all([croissant_mid, jam_mid, basket2_mid]):
            basket2_value = (self.basket2_composition["CROISSANTS"] * croissant_mid +
                             self.basket2_composition["JAMS"] * jam_mid)

            if basket2_mid > basket2_value + self.profit_buffer:
                # Basket overpriced: Sell basket, buy components
                if self.within_limits(state, "PICNIC_BASKET2", -1):
                    best_bid = max(state.order_depths["PICNIC_BASKET2"].buy_orders.keys())
                    volume = min(state.order_depths["PICNIC_BASKET2"].buy_orders[best_bid],
                               self.position_limits["PICNIC_BASKET2"] - abs(state.position.get("PICNIC_BASKET2", 0)))
                    if volume > 0:
                        orders["PICNIC_BASKET2"] = [Order("PICNIC_BASKET2", best_bid, -volume)]
                        # Buy components
                        for product, qty in self.basket2_composition.items():
                            if self.within_limits(state, product, volume * qty):
                                best_ask = min(state.order_depths[product].sell_orders.keys())
                                avail_volume = min(state.order_depths[product].sell_orders[best_ask], volume * qty)
                                if avail_volume > 0:
                                    orders[product] = orders.get(product, []) + [Order(product, best_ask, avail_volume)]

            elif basket2_mid < basket2_value - self.profit_buffer:
                # Basket underpriced: Buy basket, sell components
                if self.within_limits(state, "PICNIC_BASKET2", 1):
                    best_ask = min(state.order_depths["PICNIC_BASKET2"].sell_orders.keys())
                    volume = min(state.order_depths["PICNIC_BASKET2"].sell_orders[best_ask],
                               self.position_limits["PICNIC_BASKET2"] - abs(state.position.get("PICNIC_BASKET2", 0)))
                    if volume > 0:
                        orders["PICNIC_BASKET2"] = [Order("PICNIC_BASKET2", best_ask, volume)]
                        # Sell components
                        for product, qty in self.basket2_composition.items():
                            if self.within_limits(state, product, -volume * qty):
                                best_bid = max(state.order_depths[product].buy_orders.keys())
                                avail_volume = min(state.order_depths[product].buy_orders[best_bid], volume * qty)
                                if avail_volume > 0:
                                    orders[product] = orders.get(product, []) + [Order(product, best_bid, -avail_volume)]

        return orders, 0, "ENHANCED_ARBITRAGE"