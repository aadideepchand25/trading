import numpy as np

class Broker:
    def __init__(self, portfolio, initial, hedging = False, verbose = True):
        self.cash = initial
        self.tickers = portfolio
        self.portfolio = dict.fromkeys(portfolio, 0)
        self.price = dict.fromkeys(portfolio, 0)
        self.history = []
        self.order = {ticker: [] for ticker in portfolio}
        self.open = {ticker: [] for ticker in portfolio}
        self.hedging = hedging
        self.time = 0
        self.first = True
        if not verbose:
            import builtins
            builtins.print = lambda *args, **kwargs: None
            
    def update_price(self, data):
        self.price = dict(zip(self.tickers, data))
        if self.first:
            self.log()
            self.first = False
        self.time += 1
    
    def fee(self, shares):
        fee = max(shares * 0.005, 1)
        return fee
        
    def update(self):
        #Process open positions
        for t, positions in self.open.items():
            price = self.price[t]
            for pos in positions[:]:
                action, share, id, tp, sl, p = pos
                if action == "LNG":
                    if price > tp or price < sl:
                        self.cash += share * price
                        self.order[t].append(("CLS", id))
                        self.open[t].remove(pos)
                        print(f"(t = {self.time}) Order ID: {id} - Automatic close triggered successfully")
                elif action == "SHT":
                    if price < tp or price > sl:
                        self.cash -= share * price
                        self.order[t].append(("CLS", id))
                        self.open[t].remove(pos)
                        print(f"(t = {self.time}) Order ID: {id} - Automatic close triggered successfully")
        
        #Handle current orderbook state
        for t, orders in self.order.items():
            if len(orders) == 0:
                continue
            actions = [o[0] for o in orders]
            if ("B" in actions and "S" in actions):
                print(f"(t = {self.time}) ERROR - Could not process order book ({t}): Attempting to buy and sell simultaneously")
                return
            if not self.hedging and ("LNG" in actions and "SHT" in actions) or ("B" in actions and "SHT" in actions) or ("S" in actions and "LNG" in actions):
                print(f"(t = {self.time}) ERROR - Could not process order book ({t}): Attempting illegal operation without hedging mode")
                return
            buy = sum([o[1] for o in orders if o[0] == "B"])
            long = [o for o in orders if o[0] == "LNG"]
            sell = sum([o[1] for o in orders if o[0] == "S"])  
            short = [o for o in orders if o[0] == "SHT"]
            price = self.price[t]
            if self.cash >= self.fee(buy + sell + sum([l[1] for l in long]) + sum([s[1] for s in short])) + ((buy + sum([l[1] for l in long]) + (sum([s[1] for s in short]) * 1.5)) * price) and self.portfolio[t] + buy >= sell:
                self.cash += (sell - buy + sum([s[1] for s in short]) - sum([l[1] for l in long])) * price
                self.portfolio[t] += (buy - sell)
                self.open[t] += short + long
                print(f"(t = {self.time}) Orders on {t} carried out successfully:")
                margin = len(f"(t = {self.time}) ")
                for o in orders:
                    print(f"{' '*margin}{o}")
                continue
            print(f"(t = {self.time}) ERROR - Could not process order book ({t}): Invalid cash or shares to execute orderbook")
   
        self.log()
        self.order = {ticker: [] for ticker in self.tickers}

    def buy(self, ticker, share):
        self.order[ticker].append(("B", share))
    
    def sell(self, ticker, share):
        self.order[ticker].append(("S", share))     
            
    def long(self, ticker, share, id, tp, sl):
        if not self.hedging and "SHT" in [o[0] for o in self.open[ticker]]:
            print(f"(t = {self.time}) ERROR - Could not process order book: Attempting to maintain long and short position without hedging mode")
            return
        if id in [o[2] for o in self.open[ticker]]:
            print(f"(t = {self.time}) ERROR - Could not process order book: Attempting to reuse existing ID")
            return
        self.order[ticker].append(("LNG", share, id, float(tp), float(sl), self.price[ticker]))
            
    def short(self, ticker, share, id, tp, sl):
        if not self.hedging and "LNG" in [o[0] for o in self.open[ticker]]:
            print(f"(t = {self.time}) ERROR - Could not process order book: Attempting to maintain long and short position without hedging mode")
            return
        if id in [o[2] for o in self.open[ticker]]:
            print(f"(t = {self.time}) ERROR - Could not process order book: Attempting to reuse existing ID")
            return
        self.order[ticker].append(("SHT", share, id, float(tp), float(sl), self.price[ticker]))
            
    def close(self, id):
        for t, positions in self.open.items():
            for pos in positions[:]:
                action, share, name, tp, sl, p = pos
                if name == id:
                    price = self.price[t]
                    if action == "LNG":
                        self.cash += share * price
                        self.order[t].append(("CLS", id))
                        self.open[t].remove(pos)
                        print(f"(t = {self.time}) Order ID: {id} - Manual close completed successfully")
                        return
                    elif action == "SHT":
                        self.cash -= share * price
                        self.order[t].append(("CLS", id))
                        self.open[t].remove(pos)
                        print(f"(t = {self.time}) Order ID: {id} - Manual close completed successfully")
                        return
        print(f"(t = {self.time}) ERROR - Was unable to find an order with that ID")

    def open_value(self):
        value = []
        for t in self.tickers:
            price = self.price[t]
            val = 0
            for p in self.open[t]:
                if p[0] == "SHT":
                    val += (p[5] - price) * p[1]
                elif p[0] == "LNG":
                    val += (price - p[5]) * p[1]
            value.append(val)
        return np.array(value)
    
    def value(self):
        value = []
        for t in self.tickers:
            price = self.price[t]
            val = self.portfolio[t] * price
            for p in self.open[t]:
                if p[0] == "SHT":
                    val -= p[1] * price
                elif p[0] == "LNG":
                    val += p[1] * price
            value.append(val)
        return np.array(value)

    def log(self):
        self.history.append({
            'equity': self.cash + sum(self.value()),
            'portfolio': self.open_value(),
            'current': [self.price[t] for t in self.tickers],
            'orders': self.order
        })