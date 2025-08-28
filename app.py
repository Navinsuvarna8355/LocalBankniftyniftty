import { useState, useEffect } from 'react';
import { initializeApp } from 'firebase/app';
import { getAuth, signInAnonymously, signInWithCustomToken } from 'firebase/auth';
import { getFirestore, doc, onSnapshot, setDoc, query, collection, addDoc, serverTimestamp, orderBy, limit } from 'firebase/firestore';

// Tailwind CSS is assumed to be available
const App = () => {
  const [dataCache, setDataCache] = useState({ NIFTY: null, BANKNIFTY: null });
  const [tradeLog, setTradeLog] = useState([]);
  const [isAuthReady, setIsAuthReady] = useState(false);
  const [db, setDb] = useState(null);
  const [auth, setAuth] = useState(null);
  const [userId, setUserId] = useState(null);
  const [paperTradingOn, setPaperTradingOn] = useState(false);

  // Hardcoded dummy data to simulate API response and avoid 401 errors
  // You can replace this with your actual API call in the future
  const dummyData = {
    NIFTY: {
      underlying: 22500.50,
      pcr_total: 1.2,
      pcr_near: 1.15,
      trend: "BULLISH",
      signal: "BUY",
      suggested_side: "CALL",
      vix_data: { value: 18.5, label: "Medium Volatility", advice: "The market has medium volatility. You can trade according to your strategy." },
      oi_levels: { resistance: 22600, support: 22400 },
    },
    BANKNIFTY: {
      underlying: 48500.75,
      pcr_total: 0.85,
      pcr_near: 0.9,
      trend: "BEARISH",
      signal: "SELL",
      suggested_side: "PUT",
      vix_data: { value: 18.5, label: "Medium Volatility", advice: "The market has medium volatility. You can trade according to your strategy." },
      oi_levels: { resistance: 48600, support: 48400 },
    },
  };

  // 1. Firebase Initialization & Authentication
  useEffect(() => {
    const initializeFirebase = async () => {
      try {
        const firebaseConfig = typeof __firebase_config !== 'undefined' ? JSON.parse(__firebase_config) : {};
        const app = initializeApp(firebaseConfig);
        const firestoreDb = getFirestore(app);
        const firebaseAuth = getAuth(app);
        setDb(firestoreDb);
        setAuth(firebaseAuth);

        const initialAuthToken = typeof __initial_auth_token !== 'undefined' ? __initial_auth_token : null;
        if (initialAuthToken) {
          await signInWithCustomToken(firebaseAuth, initialAuthToken);
        } else {
          await signInAnonymously(firebaseAuth);
        }

        firebaseAuth.onAuthStateChanged(user => {
          if (user) {
            setUserId(user.uid);
            setIsAuthReady(true);
            console.log("Firebase authenticated successfully with UID:", user.uid);
          } else {
            console.log("Firebase authentication failed or is not ready.");
            setIsAuthReady(false);
          }
        });
      } catch (error) {
        console.error("Firebase initialization or auth error:", error);
      }
    };

    initializeFirebase();
  }, []);

  // 2. Real-time data fetching from Firestore
  useEffect(() => {
    if (!db || !isAuthReady) return;

    // Use a fixed collection path for the live data source
    const docRef = doc(db, 'live_data', 'market_data');

    const unsubscribe = onSnapshot(docRef, (docSnap) => {
      if (docSnap.exists()) {
        const liveData = docSnap.data();
        console.log("Live data fetched from Firestore:", liveData);
        setDataCache(liveData);
      } else {
        console.log("No live data document found. Using dummy data.");
        setDataCache(dummyData);
      }
    }, (error) => {
      console.error("Error fetching live data from Firestore:", error);
      // Fallback to dummy data on error
      setDataCache(dummyData);
    });

    // Cleanup listener on component unmount
    return () => unsubscribe();
  }, [db, isAuthReady]);

  // 3. Trade Log listener
  useEffect(() => {
    if (!db || !isAuthReady || !userId) return;

    // Collection path for private user data
    const tradeLogCollectionPath = `artifacts/${typeof __app_id !== 'undefined' ? __app_id : 'default'}/users/${userId}/trade_log`;
    const q = query(collection(db, tradeLogCollectionPath));
    
    const unsubscribe = onSnapshot(q, (querySnapshot) => {
      const logs = [];
      querySnapshot.forEach((doc) => {
        logs.push({ ...doc.data(), id: doc.id });
      });
      // Sort by timestamp descending
      logs.sort((a, b) => (b.timestamp?.seconds || 0) - (a.timestamp?.seconds || 0));
      setTradeLog(logs);
      console.log("Trade log updated from Firestore.");
    }, (error) => {
      console.error("Error fetching trade log from Firestore:", error);
    });

    return () => unsubscribe();
  }, [db, isAuthReady, userId]);

  // 4. Trading logic and Firestore writes
  useEffect(() => {
    if (!isAuthReady || !db || !userId || !paperTradingOn) return;

    const runTradingLogic = async () => {
      const now = new Date();
      const lastUpdate = new Date(tradeLog[0]?.timestamp?.toDate() || 0);
      // Only run logic if a minute has passed since the last log entry
      if (now.getTime() - lastUpdate.getTime() < 60000) return;
      
      const newTrades = [];
      const updatedTrades = [];

      // Check for trade entries
      for (const symbol of ['NIFTY', 'BANKNIFTY']) {
        const currentInfo = dataCache[symbol];
        if (!currentInfo) continue;

        const activeTrade = tradeLog.find(trade => trade.Symbol === symbol && trade.Status === 'Active');
        const finalSignal = currentInfo.signal;

        if (!activeTrade && finalSignal !== 'SIDEWAYS') {
          const newEntry = {
            timestamp: serverTimestamp(),
            Symbol: symbol,
            Signal: finalSignal,
            EntryPrice: currentInfo.underlying,
            Status: 'Active',
            P_L: 0,
            FinalP_L: null,
            Trigger: 'Strategy',
          };
          newTrades.push(newEntry);
        }
      }

      // Check for trade exits and update P&L
      for (const trade of tradeLog) {
        if (trade.Status === 'Active') {
          const currentInfo = dataCache[trade.Symbol];
          if (!currentInfo) continue;

          const currentPrice = currentInfo.underlying;
          const currentSignal = currentInfo.signal;

          const isExitSignal = currentSignal === 'SIDEWAYS' || (currentSignal !== trade.Signal);

          const livePnL = trade.Signal === 'BUY'
            ? currentPrice - trade.EntryPrice
            : trade.EntryPrice - currentPrice;

          if (isExitSignal) {
            const finalPnL = trade.Signal === 'BUY'
              ? currentPrice - trade.EntryPrice
              : trade.EntryPrice - currentPrice;

            updatedTrades.push({
              ...trade,
              Status: 'Closed',
              P_L: livePnL,
              FinalP_L: finalPnL,
            });
          } else {
            updatedTrades.push({
              ...trade,
              P_L: livePnL,
            });
          }
        }
      }

      // Perform Firestore writes
      const tradeLogCollectionPath = `artifacts/${typeof __app_id !== 'undefined' ? __app_id : 'default'}/users/${userId}/trade_log`;
      try {
        await Promise.all(newTrades.map(trade => addDoc(collection(db, tradeLogCollectionPath), trade)));
        await Promise.all(updatedTrades.map(trade => setDoc(doc(db, tradeLogCollectionPath, trade.id), trade)));
        console.log("Firestore writes completed.");
      } catch (error) {
        console.error("Error writing to Firestore:", error);
      }
    };
    
    const intervalId = setInterval(runTradingLogic, 60000); // Run every minute
    return () => clearInterval(intervalId);

  }, [isAuthReady, db, userId, paperTradingOn, dataCache, tradeLog]);

  const dashboardSection = (symbol) => {
    const info = dataCache[symbol];
    if (!info) return <div className="p-4 bg-gray-100 rounded-xl shadow-lg w-full">Loading...</div>;

    const signalColor = info.signal === "BUY" ? "bg-green-500" : info.signal === "SELL" ? "bg-red-500" : "bg-blue-500";
    const signalText = info.signal === "BUY" ? "BUY CE" : info.signal === "SELL" ? "SELL PE" : "SIDEWAYS";
    const signalAdvice = info.signal === "BUY" ? `ATM Option: ₹${Math.round(info.underlying / 100) * 100} CE` :
      info.signal === "SELL" ? `ATM Option: ₹${Math.round(info.underlying / 100) * 100} PE` : "No strong signal found.";

    return (
      <div className="p-6 bg-white rounded-3xl shadow-2xl transition-transform transform hover:scale-105 duration-300 w-full flex flex-col items-center border border-gray-200">
        <h2 className="text-3xl font-bold text-gray-800 mb-4">{symbol} Dashboard</h2>
        <div className="flex justify-between w-full mb-6 text-center">
          <div className="flex-1 p-2">
            <p className="text-sm text-gray-500">Live Price</p>
            <p className="text-2xl font-semibold text-gray-900">₹ {info.underlying?.toFixed(2)}</p>
          </div>
          <div className="flex-1 p-2">
            <p className="text-sm text-gray-500">PCR</p>
            <p className="text-2xl font-semibold text-gray-900">{info.pcr_total?.toFixed(2)}</p>
          </div>
          <div className="flex-1 p-2">
            <p className="text-sm text-gray-500">Trend</p>
            <p className={`text-2xl font-semibold ${info.trend === 'BULLISH' ? 'text-green-600' : 'text-red-600'}`}>{info.trend}</p>
          </div>
        </div>
        <div className={`w-full p-4 rounded-xl text-center text-white font-bold text-lg mb-6 ${signalColor}`}>
          <p>Signal: {signalText}</p>
          <p className="text-sm font-light mt-1">{signalAdvice}</p>
        </div>
        <div className="w-full text-center">
          <h3 className="text-xl font-bold text-gray-800 mb-2">OI-Based S&R</h3>
          <div className="flex justify-around w-full">
            <div className="flex-1 p-2">
              <p className="text-sm text-gray-500">Resistance</p>
              <p className="text-xl font-semibold text-red-600">₹ {info.oi_levels.resistance}</p>
            </div>
            <div className="flex-1 p-2">
              <p className="text-sm text-gray-500">Support</p>
              <p className="text-xl font-semibold text-green-600">₹ {info.oi_levels.support}</p>
            </div>
          </div>
        </div>
      </div>
    );
  };
  
  const TradeLogTable = () => {
    if (tradeLog.length === 0) return <div className="text-center text-gray-500 mt-8">Trade log is empty.</div>;
    
    return (
      <div className="overflow-x-auto w-full mt-8 rounded-xl shadow-lg">
        <table className="min-w-full divide-y divide-gray-200">
          <thead className="bg-gray-50">
            <tr>
              {['Timestamp', 'Symbol', 'Signal', 'Entry Price', 'P&L (Live/Final)', 'Status'].map(header => (
                <th key={header} className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  {header}
                </th>
              ))}
            </tr>
          </thead>
          <tbody className="bg-white divide-y divide-gray-200">
            {tradeLog.map((trade) => {
              const pnl = trade.Status === 'Active' ? trade.P_L : trade.FinalP_L;
              const pnlColor = pnl > 0 ? 'text-green-600' : pnl < 0 ? 'text-red-600' : 'text-gray-500';
              return (
                <tr key={trade.id} className="hover:bg-gray-50 transition-colors">
                  <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                    {new Date(trade.timestamp?.seconds * 1000).toLocaleString()}
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap text-sm font-medium text-gray-900">{trade.Symbol}</td>
                  <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">{trade.Signal}</td>
                  <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">₹{trade.EntryPrice?.toFixed(2)}</td>
                  <td className={`px-6 py-4 whitespace-nowrap text-sm font-bold ${pnlColor}`}>
                    ₹{pnl?.toFixed(2)}
                  </td>
                  <td className={`px-6 py-4 whitespace-nowrap text-sm font-semibold ${trade.Status === 'Active' ? 'text-green-500' : 'text-red-500'}`}>
                    {trade.Status}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    );
  };

  return (
    <div className="min-h-screen bg-gray-50 p-8 font-sans antialiased">
      <div className="max-w-7xl mx-auto">
        <div className="flex flex-col items-center text-center mb-12">
          <h1 className="text-5xl font-extrabold text-gray-900 mb-2">NSE Auto Paper Trading</h1>
          <p className="text-lg text-gray-600 max-w-2xl">
            This dashboard simulates **automatic paper trades** for NIFTY and BANKNIFTY based on a custom strategy.
          </p>
          <div className="mt-6 p-4 rounded-xl bg-yellow-100 border border-yellow-200 text-yellow-800 font-medium w-full max-w-lg">
            Disclaimer: This is for educational purposes only. Do not use for live trading.
          </div>
          <div className="mt-6 flex items-center space-x-4">
            <span className="text-xl font-bold text-gray-700">Paper Trading ON/OFF</span>
            <label htmlFor="toggle-trade" className="flex items-center cursor-pointer">
              <div className="relative">
                <input
                  type="checkbox"
                  id="toggle-trade"
                  className="sr-only"
                  checked={paperTradingOn}
                  onChange={() => setPaperTradingOn(!paperTradingOn)}
                />
                <div className={`block ${paperTradingOn ? 'bg-green-500' : 'bg-gray-300'} w-14 h-8 rounded-full transition-colors duration-300`}></div>
                <div className={`dot absolute left-1 top-1 bg-white w-6 h-6 rounded-full transition-transform duration-300 ${paperTradingOn ? 'translate-x-6' : ''}`}></div>
              </div>
            </label>
          </div>
          {userId && (
            <div className="mt-4 text-sm text-gray-500">
              <p>User ID: <span className="font-mono bg-gray-200 p-1 rounded-md">{userId}</span></p>
            </div>
          )}
        </div>
        <div className="grid md:grid-cols-2 gap-8 mb-12">
          {dashboardSection('NIFTY')}
          {dashboardSection('BANKNIFTY')}
        </div>
        <div className="bg-white rounded-3xl shadow-2xl p-8 border border-gray-200">
          <h2 className="text-3xl font-bold text-gray-800 mb-4 text-center">India VIX</h2>
          <div className="w-full p-4 rounded-xl bg-blue-100 text-blue-800 text-center font-semibold">
            <p className="text-xl">India VIX: <span className="font-extrabold">{dataCache.NIFTY?.vix_data.value.toFixed(2)}</span> ({dataCache.NIFTY?.vix_data.label})</p>
            <p className="text-sm mt-1">{dataCache.NIFTY?.vix_data.advice}</p>
          </div>
        </div>
        <div className="mt-12 bg-white rounded-3xl shadow-2xl p-8 border border-gray-200">
          <h2 className="text-3xl font-bold text-gray-800 mb-6 text-center">Trade Log</h2>
          <TradeLogTable />
        </div>
      </div>
    </div>
  );
};

export default App;
