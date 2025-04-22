from datamodel import OrderDepth, TradingState, Order
from typing import Dict, List, Tuple
import json

class Trader:
    def __init__(self):
        # Initialize trader state
        self.position_limits = {
            "PICNIC_BASKET1": 60, "PICNIC_BASKET2": 100,
            "CROISSANTS": 250, "JAMS": 350, "DJEMBES": 60
        }
        self.base_profit_buffer = 1.5
        self.basket1_composition = {"CROISSANTS": 6, "JAMS": 3, "DJEMBES": 1}
        self.basket2_composition = {"CROISSANTS": 4, "JAMS": 2}
        self.counterparty_profiles = self.initialize_counterparty_profiles()
        
    def initialize_counterparty_profiles(self):
        profiles = {}
        # Ant traders - generally good at technical trading
        ant_traders = ["Amir", "Ayumi", "Ari", "Anika"]
        for trader in ant_traders:
            profiles[trader] = {"risk_level": "medium", "trust_score": 0.7, "strategy": "technical"}
        
        # Beetle traders - aggressive hoarders
        beetle_traders = ["Boris", "Bashir", "Bonnie", "Blue"]
        for trader in beetle_traders:
            profiles[trader] = {"risk_level": "high", "trust_score": 0.5, "strategy": "momentum"}
        
        # Spider traders - methodical and patient
        spider_traders = ["Sanjay", "Sami", "Sierra", "Santiago"]
        for trader in spider_traders:
            profiles[trader] = {"risk_level": "low", "trust_score": 0.8, "strategy": "value"}
        
        # Mosquito traders - quick but unpredictable
        mosquito_traders = ["Mikhail", "Mina", "Morgan", "Manuel"]
        for trader in mosquito_traders:
            profiles[trader] = {"risk_level": "high", "trust_score": 0.4, "strategy": "high_frequency"}
        
        # Cockroach traders - resilient and survivors
        cockroach_traders = ["Carlos", "Candice", "Carson", "Cristiano"]
        for trader in cockroach_traders:
            profiles[trader] = {"risk_level": "medium", "trust_score": 0.6, "strategy": "contrarian"}
            
        return profiles

    def get_mid(self, product: str, state: TradingState) -> float:
        """Calculate the mid price of a product."""
        if product not in state.order_depths:
            return None
        bids = state.order_depths[product].buy_orders
        asks = state.order_depths[product].sell_orders
        if bids and asks:
            return (max(bids.keys()) + min(asks.keys())) / 2
        return None

    def within_limits(self, state: TradingState, product: str, qty: int) -> bool:
        """Check if a potential trade is within position limits."""
        current_position = state.position.get(product, 0)
        new_position = current_position + qty
        return abs(new_position) <= self.position_limits[product]
    
    def analyze_counterparties(self, state: TradingState):
        """Analyze counterparties from recent trades."""
        counterparty_data = {}
        
        # Extract counterparty info from recent trades
        for product, trades in state.own_trades.items():
            for trade in trades:
                counterparty = trade.counter_party
                if not counterparty:
                    continue
                    
                if counterparty not in counterparty_data:
                    counterparty_data[counterparty] = {"products": {}}
                
                if product not in counterparty_data[counterparty]["products"]:
                    counterparty_data[counterparty]["products"][product] = []
                    
                counterparty_data[counterparty]["products"][product].append({
                    "price": trade.price,
                    "quantity": trade.quantity
                })
                
                # Add profile data if available
                if counterparty in self.counterparty_profiles:
                    counterparty_data[counterparty]["profile"] = self.counterparty_profiles[counterparty]
        
        return counterparty_data
        
    def get_trader_state(self, state: TradingState):
        """Parse the trader state data."""
        if not state.traderData:
            return {
                "price_history": {},
                "counterparty_performance": {},
                "preferred_counterparties": {}
            }
        
        try:
            return json.loads(state.traderData)
        except:
            return {
                "price_history": {},
                "counterparty_performance": {},
                "preferred_counterparties": {}
            }
            
    def update_price_history(self, trader_state, state: TradingState):
        """Update price history in trader state."""
        if "price_history" not in trader_state:
            trader_state["price_history"] = {}
            
        for product in self.position_limits:
            if product not in trader_state["price_history"]:
                trader_state["price_history"][product] = []
                
            mid = self.get_mid(product, state)
            if mid:
                trader_state["price_history"][product].append(mid)
                if len(trader_state["price_history"][product]) > 5:  # Keep last 5 prices
                    trader_state["price_history"][product].pop(0)
                    
        return trader_state

    def update_counterparty_data(self, trader_state, state: TradingState):
        """Update counterparty data in trader state."""
        if "counterparty_performance" not in trader_state:
            trader_state["counterparty_performance"] = {}
            
        for product, trades in state.own_trades.items():
            for trade in trades:
                counterparty = trade.counter_party
                if not counterparty:
                    continue
                    
                if counterparty not in trader_state["counterparty_performance"]:
                    trader_state["counterparty_performance"][counterparty] = {}
                    
                if product not in trader_state["counterparty_performance"][counterparty]:
                    trader_state["counterparty_performance"][counterparty][product] = 0.0
                    
                # Update P&L based on trade
                mid_price = self.get_mid(product, state)
                if mid_price:
                    # Calculate profit/loss based on difference between trade price and mid price
                    trade_value = trade.quantity * (mid_price - trade.price)
                    trader_state["counterparty_performance"][counterparty][product] += trade_value
                    
        return trader_state
        
    def update_preferred_counterparties(self, trader_state):
        """Update preferred counterparties list."""
        if "preferred_counterparties" not in trader_state:
            trader_state["preferred_counterparties"] = {}
            
        if "counterparty_performance" not in trader_state:
            return trader_state
            
        for counterparty, products in trader_state["counterparty_performance"].items():
            for product, performance in products.items():
                if product not in trader_state["preferred_counterparties"]:
                    trader_state["preferred_counterparties"][product] = []
                
                # Add to preferred list if not already there and performance is good
                if performance > 0 and counterparty not in trader_state["preferred_counterparties"][product]:
                    trader_state["preferred_counterparties"][product].append(counterparty)
                
                # Remove if performance becomes negative
                elif performance < 0 and counterparty in trader_state["preferred_counterparties"][product]:
                    trader_state["preferred_counterparties"][product].remove(counterparty)
                    
        return trader_state
    
    def get_counterparty_trust(self, trader_state, product: str, counterparty: str) -> float:
        """Calculate trust score for a counterparty."""
        if counterparty not in self.counterparty_profiles:
            return 1.0  # Default for unknown counterparties
        
        # Get base trust score from profile
        trust_score = self.counterparty_profiles[counterparty]["trust_score"]
        
        # Adjust based on trading history if available
        if "counterparty_performance" in trader_state and counterparty in trader_state["counterparty_performance"]:
            if product in trader_state["counterparty_performance"][counterparty]:
                performance = trader_state["counterparty_performance"][counterparty][product]
                # Increase trust for profitable counterparties, decrease for unprofitable ones
                trust_modifier = min(max(performance / 1000, -0.3), 0.3)  # Cap adjustment at ±0.3
                trust_score += trust_modifier
        
        # Normalize to a reasonable range
        return min(max(trust_score, 0.5), 1.5)

    def run(self, state: TradingState):
        print("traderData: " + state.traderData)
        print("Observations: " + str(state.observations))
        
        # Parse trader state data
        trader_state = self.get_trader_state(state)
        
        # Update state with new data
        trader_state = self.update_price_history(trader_state, state)
        trader_state = self.update_counterparty_data(trader_state, state)
        trader_state = self.update_preferred_counterparties(trader_state)
        
        # Analyze counterparties
        counterparty_analysis = self.analyze_counterparties(state)
        
        # Orders to be placed on exchange matching engine
        result = {}
        
        # Get mid prices for basket components
        croissant_mid = self.get_mid("CROISSANTS", state)
        jam_mid = self.get_mid("JAMS", state)
        djembe_mid = self.get_mid("DJEMBES", state)
        basket1_mid = self.get_mid("PICNIC_BASKET1", state)
        basket2_mid = self.get_mid("PICNIC_BASKET2", state)
        
        # Profit buffers for arbitrage
        profit_buffer1 = 1.5
        profit_buffer2 = 1.5
        
        # Process each product
        for product in state.order_depths:
            order_depth: OrderDepth = state.order_depths[product]
            orders: List[Order] = []
            
            print("Buy Order depth : " + str(len(order_depth.buy_orders)) + ", Sell order depth : " + str(len(order_depth.sell_orders)))
            
            # PICNIC_BASKET1 Arbitrage
            if product == "PICNIC_BASKET1" and all([croissant_mid, jam_mid, djembe_mid, basket1_mid]):
                basket1_value = (self.basket1_composition["CROISSANTS"] * croissant_mid +
                                self.basket1_composition["JAMS"] * jam_mid +
                                self.basket1_composition["DJEMBES"] * djembe_mid)
                
                spread = basket1_mid - basket1_value
                
                # Determine acceptable price based on arbitrage opportunity
                if spread > profit_buffer1:  # Sell basket (overpriced)
                    acceptable_price = basket1_value + profit_buffer1
                    print("Acceptable sell price for PICNIC_BASKET1: " + str(acceptable_price))
                    
                    if len(order_depth.buy_orders) != 0:
                        best_bid = max(order_depth.buy_orders.keys())
                        best_bid_amount = order_depth.buy_orders[best_bid]
                        
                        if best_bid > acceptable_price:
                            # Adjust volume based on counterparty trust if available
                            adjusted_amount = best_bid_amount
                            if "own_trades" in state and "PICNIC_BASKET1" in state.own_trades:
                                recent_counterparties = [t.counter_party for t in state.own_trades["PICNIC_BASKET1"]]
                                if recent_counterparties:
                                    trust_factor = sum(self.get_counterparty_trust(trader_state, "PICNIC_BASKET1", cp) 
                                                      for cp in recent_counterparties) / len(recent_counterparties)
                                    adjusted_amount = int(best_bid_amount * trust_factor)
                            
                            # Ensure position limits
                            sell_volume = min(adjusted_amount, self.position_limits["PICNIC_BASKET1"] - 
                                             abs(state.position.get("PICNIC_BASKET1", 0)))
                            
                            if sell_volume > 0:
                                print("SELL PICNIC_BASKET1", str(sell_volume) + "x", best_bid)
                                orders.append(Order(product, best_bid, -sell_volume))
                                
                elif spread < -profit_buffer1:  # Buy basket (underpriced)
                    acceptable_price = basket1_value - profit_buffer1
                    print("Acceptable buy price for PICNIC_BASKET1: " + str(acceptable_price))
                    
                    if len(order_depth.sell_orders) != 0:
                        best_ask = min(order_depth.sell_orders.keys())
                        best_ask_amount = order_depth.sell_orders[best_ask]
                        
                        if best_ask < acceptable_price:
                            # Adjust volume based on counterparty trust if available
                            adjusted_amount = best_ask_amount
                            if "own_trades" in state and "PICNIC_BASKET1" in state.own_trades:
                                recent_counterparties = [t.counter_party for t in state.own_trades["PICNIC_BASKET1"]]
                                if recent_counterparties:
                                    trust_factor = sum(self.get_counterparty_trust(trader_state, "PICNIC_BASKET1", cp) 
                                                      for cp in recent_counterparties) / len(recent_counterparties)
                                    adjusted_amount = int(best_ask_amount * trust_factor)
                            
                            # Ensure position limits
                            buy_volume = min(adjusted_amount, self.position_limits["PICNIC_BASKET1"] - 
                                           abs(state.position.get("PICNIC_BASKET1", 0)))
                            
                            if buy_volume > 0:
                                print("BUY PICNIC_BASKET1", str(buy_volume) + "x", best_ask)
                                orders.append(Order(product, best_ask, buy_volume))
            
            # PICNIC_BASKET2 Arbitrage
            elif product == "PICNIC_BASKET2" and all([croissant_mid, jam_mid, basket2_mid]):
                basket2_value = (self.basket2_composition["CROISSANTS"] * croissant_mid +
                                self.basket2_composition["JAMS"] * jam_mid)
                
                spread = basket2_mid - basket2_value
                
                # Determine acceptable price based on arbitrage opportunity
                if spread > profit_buffer2:  # Sell basket (overpriced)
                    acceptable_price = basket2_value + profit_buffer2
                    print("Acceptable sell price for PICNIC_BASKET2: " + str(acceptable_price))
                    
                    if len(order_depth.buy_orders) != 0:
                        best_bid = max(order_depth.buy_orders.keys())
                        best_bid_amount = order_depth.buy_orders[best_bid]
                        
                        if best_bid > acceptable_price:
                            # Adjust volume based on counterparty trust if available
                            adjusted_amount = best_bid_amount
                            if "own_trades" in state and "PICNIC_BASKET2" in state.own_trades:
                                recent_counterparties = [t.counter_party for t in state.own_trades["PICNIC_BASKET2"]]
                                if recent_counterparties:
                                    trust_factor = sum(self.get_counterparty_trust(trader_state, "PICNIC_BASKET2", cp) 
                                                      for cp in recent_counterparties) / len(recent_counterparties)
                                    adjusted_amount = int(best_bid_amount * trust_factor)
                            
                            # Ensure position limits
                            sell_volume = min(adjusted_amount, self.position_limits["PICNIC_BASKET2"] - 
                                             abs(state.position.get("PICNIC_BASKET2", 0)))
                            
                            if sell_volume > 0:
                                print("SELL PICNIC_BASKET2", str(sell_volume) + "x", best_bid)
                                orders.append(Order(product, best_bid, -sell_volume))
                                
                elif spread < -profit_buffer2:  # Buy basket (underpriced)
                    acceptable_price = basket2_value - profit_buffer2
                    print("Acceptable buy price for PICNIC_BASKET2: " + str(acceptable_price))
                    
                    if len(order_depth.sell_orders) != 0:
                        best_ask = min(order_depth.sell_orders.keys())
                        best_ask_amount = order_depth.sell_orders[best_ask]
                        
                        if best_ask < acceptable_price:
                            # Adjust volume based on counterparty trust if available
                            adjusted_amount = best_ask_amount
                            if "own_trades" in state and "PICNIC_BASKET2" in state.own_trades:
                                recent_counterparties = [t.counter_party for t in state.own_trades["PICNIC_BASKET2"]]
                                if recent_counterparties:
                                    trust_factor = sum(self.get_counterparty_trust(trader_state, "PICNIC_BASKET2", cp) 
                                                      for cp in recent_counterparties) / len(recent_counterparties)
                                    adjusted_amount = int(best_ask_amount * trust_factor)
                            
                            # Ensure position limits
                            buy_volume = min(adjusted_amount, self.position_limits["PICNIC_BASKET2"] - 
                                           abs(state.position.get("PICNIC_BASKET2", 0)))
                            
                            if buy_volume > 0:
                                print("BUY PICNIC_BASKET2", str(buy_volume) + "x", best_ask)
                                orders.append(Order(product, best_ask, buy_volume))
            
            # Component trading - only when needed for basket arbitrage or when good opportunity exists
            elif product in ["CROISSANTS", "JAMS", "DJEMBES"]:
                # Simple default trading logic
                acceptable_price = 10  # Default value
                
                # Adjust acceptable price based on recent market data
                mid_price = self.get_mid(product, state)
                if mid_price:
                    acceptable_price = mid_price
                
                print("Acceptable price for " + product + ": " + str(acceptable_price))
                
                # Buy underpriced components
                if len(order_depth.sell_orders) != 0:
                    best_ask = min(order_depth.sell_orders.keys())
                    best_ask_amount = order_depth.sell_orders[best_ask]
                    
                    if best_ask < acceptable_price * 0.98:  # 2% discount
                        adjusted_amount = best_ask_amount
                        
                        # Adjust volume based on counterparty analysis
                        if "own_trades" in state and product in state.own_trades:
                            recent_counterparties = [t.counter_party for t in state.own_trades[product]]
                            if recent_counterparties:
                                trust_factor = sum(self.get_counterparty_trust(trader_state, product, cp) 
                                                  for cp in recent_counterparties) / len(recent_counterparties)
                                adjusted_amount = int(best_ask_amount * trust_factor)
                        
                        # Check position limits
                        buy_volume = min(adjusted_amount, self.position_limits[product] - 
                                       abs(state.position.get(product, 0)))
                        
                        if buy_volume > 0 and self.within_limits(state, product, buy_volume):
                            print("BUY " + product, str(buy_volume) + "x", best_ask)
                            orders.append(Order(product, best_ask, buy_volume))
                
                # Sell overpriced components
                if len(order_depth.buy_orders) != 0:
                    best_bid = max(order_depth.buy_orders.keys())
                    best_bid_amount = order_depth.buy_orders[best_bid]
                    
                    if best_bid > acceptable_price * 1.02:  # 2% premium
                        adjusted_amount = best_bid_amount
                        
                        # Adjust volume based on counterparty analysis
                        if "own_trades" in state and product in state.own_trades:
                            recent_counterparties = [t.counter_party for t in state.own_trades[product]]
                            if recent_counterparties:
                                trust_factor = sum(self.get_counterparty_trust(trader_state, product, cp) 
                                                  for cp in recent_counterparties) / len(recent_counterparties)
                                adjusted_amount = int(best_bid_amount * trust_factor)
                        
                        # Check position limits
                        sell_volume = min(adjusted_amount, self.position_limits[product] - 
                                        abs(state.position.get(product, 0)))
                        
                        if sell_volume > 0 and self.within_limits(state, product, -sell_volume):
                            print("SELL " + product, str(sell_volume) + "x", best_bid)
                            orders.append(Order(product, best_bid, -sell_volume))
            
            # Add orders to result if there are any
            if orders:
                result[product] = orders
        
        # Special trading strategies for known counterparty behaviors
        for product in self.position_limits:
            if product in state.own_trades and state.own_trades[product]:
                # Get recent counterparties
                counterparties = [trade.counter_party for trade in state.own_trades[product] if trade.counter_party]
                
                for counterparty in set(counterparties):
                    if counterparty in self.counterparty_profiles:
                        # Check for momentum traders (beetles)
                        if self.counterparty_profiles[counterparty]["strategy"] == "momentum":
                            if product in trader_state["price_history"] and len(trader_state["price_history"][product]) >= 3:
                                trend = trader_state["price_history"][product][-1] - trader_state["price_history"][product][-3]
                                
                                # If trend is strong, place orders ahead of momentum traders
                                if abs(trend) > 1.0 and product in state.order_depths:
                                    order_depth = state.order_depths[product]
                                    
                                    # In uptrend, place early buy orders
                                    if trend > 0 and order_depth.sell_orders:
                                        best_ask = min(order_depth.sell_orders.keys())
                                        volume = min(5, self.position_limits[product] - abs(state.position.get(product, 0)))
                                        
                                        if product not in result:
                                            result[product] = []
                                        result[product].append(Order(product, best_ask, volume))
                                        print(f"MOMENTUM STRATEGY: BUY {product} {volume}x {best_ask}")
                                    
                                    # In downtrend, place early sell orders
                                    elif trend < 0 and order_depth.buy_orders:
                                        best_bid = max(order_depth.buy_orders.keys())
                                        volume = min(5, self.position_limits[product] - abs(state.position.get(product, 0)))
                                        
                                        if product not in result:
                                            result[product] = []
                                        result[product].append(Order(product, best_bid, -volume))
                                        print(f"MOMENTUM STRATEGY: SELL {product} {volume}x {best_bid}")
        
        # String value holding Trader state data required.
        # Convert trader_state to JSON string for persistence
        traderData = json.dumps(trader_state)
        
        # No conversions in this example
        conversions = 0
        
        return result, conversions, traderData