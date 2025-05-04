/**
 * Dashboard.js - Main dashboard functionality for Bitcoin Trading Bot
 */

// Global variables
let currentPrice = 0;
let portfolioData = {
    balance: 0,
    bitcoin: 0,
    portfolio_value: 0
};
let botEnabled = false;

// Update intervals
const PRICE_UPDATE_INTERVAL = 30 * 1000; // 30 seconds
const PORTFOLIO_UPDATE_INTERVAL = 30 * 1000; // 30 seconds
const TRADE_HISTORY_UPDATE_INTERVAL = 30 * 1000; // 30 seconds
const BOT_STATUS_UPDATE_INTERVAL = 60 * 1000; // 60 seconds

// Function to format currency
function formatCurrency(amount) {
    return new Intl.NumberFormat('en-US', {
        style: 'currency',
        currency: 'USD'
    }).format(amount);
}

// Function to format Bitcoin amount
function formatBitcoin(amount) {
    return amount.toFixed(8) + ' BTC';
}

// Function to refresh the current Bitcoin price
function refreshPrice() {
    fetch('/api/current_price')
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                currentPrice = data.price;
                
                // Update price display
                document.getElementById('currentPrice').textContent = formatCurrency(data.price);
                
                // Improve timestamp display with date and time in local timezone
                const dateTimeOptions = { 
                    year: 'numeric',
                    month: '2-digit',
                    day: '2-digit',
                    hour: '2-digit', 
                    minute: '2-digit',
                    second: '2-digit',
                    hour12: false,  // 24-hour format
                    timeZoneName: 'short' // Show timezone abbreviation
                };
                
                // Parse the server-provided timestamp with timezone information
                let timestamp = data.timestamp;
                
                // Add local timezone offset if missing
                if (!timestamp.includes('+') && !timestamp.includes('Z')) {
                    // Add local timezone offset for browser time
                    const localOffset = -(new Date().getTimezoneOffset());
                    const offsetHours = Math.floor(Math.abs(localOffset) / 60);
                    const offsetMinutes = Math.abs(localOffset) % 60;
                    const offsetSign = localOffset >= 0 ? '+' : '-';
                    const offsetString = `${offsetSign}${String(offsetHours).padStart(2, '0')}:${String(offsetMinutes).padStart(2, '0')}`;
                    timestamp += offsetString;
                    
                    console.log("Adding browser timezone offset to timestamp:", offsetString);
                }
                
                const localDateTime = new Date(timestamp);
                
                // Use timezone info from server if available
                if (data.timezone_offset) {
                    console.log("Server timezone offset: " + data.timezone_offset);
                }
                
                // Display formatted time with timezone indicator
                document.getElementById('lastUpdated').textContent = localDateTime.toLocaleString(undefined, dateTimeOptions);
                
                // Update moving average analysis
                document.getElementById('maCurrentPrice').textContent = formatCurrency(data.price);
                
                // Update estimated BTC amounts in trading forms
                updateEstimatedBTC();
                
                // Update moving average section if we have price history
                updateMovingAverageAnalysis();
            } else {
                console.error('Error fetching price:', data.error);
            }
        })
        .catch(error => {
            console.error('Error fetching current price:', error);
        });
}

// Function to update the portfolio information
function refreshPortfolio() {
    fetch('/api/portfolio')
        .then(response => response.json())
        .then(data => {
            portfolioData = data;
            
            // Update portfolio display
            document.getElementById('portfolioValue').textContent = formatCurrency(data.portfolio_value);
            document.getElementById('usdBalance').textContent = formatCurrency(data.balance);
            document.getElementById('btcBalance').textContent = formatBitcoin(data.bitcoin);
            
            // Update available amounts in trading forms
            document.getElementById('availableUSD').textContent = formatCurrency(data.balance);
            document.getElementById('availableBTC').textContent = formatBitcoin(data.bitcoin);
            
            // Update portfolio allocation
            const usdValue = data.balance;
            const btcValue = data.bitcoin * currentPrice;
            const totalValue = usdValue + btcValue;
            
            if (totalValue > 0) {
                const usdPercentage = (usdValue / totalValue) * 100;
                const btcPercentage = (btcValue / totalValue) * 100;
                
                const usdElement = document.getElementById('usdPercentage');
                const btcElement = document.getElementById('btcPercentage');
                
                usdElement.style.width = `${usdPercentage}%`;
                usdElement.setAttribute('aria-valuenow', usdPercentage);
                usdElement.textContent = `USD ${usdPercentage.toFixed(1)}%`;
                
                btcElement.style.width = `${btcPercentage}%`;
                btcElement.setAttribute('aria-valuenow', btcPercentage);
                btcElement.textContent = `BTC ${btcPercentage.toFixed(1)}%`;
            }
        })
        .catch(error => {
            console.error('Error fetching portfolio data:', error);
        });
}

// Function to get recent trades
function getRecentTrades() {
    fetch('/api/trade_history')
        .then(response => response.json())
        .then(data => {
            const tradesTable = document.getElementById('recentTradesTable');
            
            if (data.length === 0) {
                tradesTable.innerHTML = `
                    <tr>
                        <td colspan="5" class="text-center py-3">No trades yet</td>
                    </tr>
                `;
                return;
            }
            
            // Take only the 5 most recent trades
            const recentTrades = data.slice(0, 5);
            
            let html = '';
            recentTrades.forEach(trade => {
                const tradeType = trade.type === 'kauf' ? 'Buy' : 'Sell';
                const typeClass = trade.type === 'kauf' ? 'success' : 'danger';
                const totalValue = trade.price * trade.amount;
                
                html += `
                    <tr>
                        <td><span class="badge bg-${typeClass}">${tradeType}</span></td>
                        <td>${trade.amount.toFixed(8)}</td>
                        <td>$${trade.price.toLocaleString('en-US', { maximumFractionDigits: 2 })}</td>
                        <td>$${totalValue.toLocaleString('en-US', { maximumFractionDigits: 2 })}</td>
                        <td>${(() => {
                            // Add timezone offset if missing
                            let timestamp = trade.timestamp;
                            if (!timestamp.includes('+') && !timestamp.includes('Z')) {
                                // Add local timezone offset for browser time
                                const localOffset = -(new Date().getTimezoneOffset());
                                const offsetHours = Math.floor(Math.abs(localOffset) / 60);
                                const offsetMinutes = Math.abs(localOffset) % 60;
                                const offsetSign = localOffset >= 0 ? '+' : '-';
                                const offsetString = `${offsetSign}${String(offsetHours).padStart(2, '0')}:${String(offsetMinutes).padStart(2, '0')}`;
                                timestamp += offsetString;
                            }
                            return new Date(timestamp).toLocaleString(undefined, {
                                hour: '2-digit',
                                minute: '2-digit',
                                day: '2-digit',
                                month: '2-digit',
                                hour12: false,
                                timeZoneName: 'short'
                            });
                        })()}</td>
                    </tr>
                `;
            });
            
            tradesTable.innerHTML = html;
        })
        .catch(error => {
            console.error('Error fetching trade history:', error);
        });
}

// Function to update estimated BTC in buy/sell forms
function updateEstimatedBTC() {
    const buyAmountInput = document.getElementById('buyAmount');
    const sellAmountInput = document.getElementById('sellAmount');
    const estimatedBTC = document.getElementById('estimatedBTC');
    const estimatedSellBTC = document.getElementById('estimatedSellBTC');
    
    if (buyAmountInput && estimatedBTC && currentPrice > 0) {
        const buyAmount = parseFloat(buyAmountInput.value) || 0;
        const btcAmount = buyAmount / currentPrice;
        estimatedBTC.value = btcAmount.toFixed(8);
    }
    
    if (sellAmountInput && estimatedSellBTC && currentPrice > 0) {
        const sellAmount = parseFloat(sellAmountInput.value) || 0;
        const btcAmount = sellAmount / currentPrice;
        estimatedSellBTC.value = btcAmount.toFixed(8);
    }
}

// Function to update the bot settings display
function updateBotSettings() {
    fetch('/api/config')
        .then(response => response.json())
        .then(data => {
            document.getElementById('sellThreshold').textContent = formatCurrency(data.verkaufswert);
            document.getElementById('buyPercentage').textContent = `${(data.buying_percentage * 100).toFixed(0)}%`;
            document.getElementById('sellPercentage').textContent = `${(data.selling_percentage_moderate * 100).toFixed(0)}%/${(data.selling_percentage_high * 100).toFixed(0)}%`;
            document.getElementById('checkInterval').textContent = `${data.price_check_interval} sec`;
        })
        .catch(error => {
            console.error('Error fetching bot settings:', error);
        });
}

// Function to update the moving average analysis
function updateMovingAverageAnalysis() {
    fetch('/api/price_history?days=1')
        .then(response => response.json())
        .then(data => {
            if (data.length >= 3) {
                // Calculate simple moving average of last 3 prices
                const recentPrices = data.slice(-3).map(item => item.price);
                const movingAverage = recentPrices.reduce((a, b) => a + b, 0) / recentPrices.length;
                
                // Update display
                document.getElementById('movingAverage').textContent = formatCurrency(movingAverage);
                
                // Calculate and display difference
                const difference = currentPrice - movingAverage;
                const differenceElement = document.getElementById('priceDifference');
                differenceElement.textContent = `${difference > 0 ? '+' : ''}${formatCurrency(difference)}`;
                differenceElement.classList.remove('text-success', 'text-danger');
                differenceElement.classList.add(difference >= 0 ? 'text-success' : 'text-danger');
                
                // Update trading signal
                const signalElement = document.getElementById('tradingSignal');
                signalElement.classList.remove('alert-success', 'alert-warning', 'alert-danger', 'alert-info');
                
                let signalText = '';
                let signalClass = '';
                
                if (currentPrice > movingAverage && currentPrice <= movingAverage + 5) {
                    signalText = '<i class="fas fa-arrow-up me-2"></i>BUY SIGNAL: Price above MA (small increase)';
                    signalClass = 'alert-success';
                } else if (currentPrice > movingAverage + 5 && currentPrice <= movingAverage + 10) {
                    signalText = '<i class="fas fa-arrow-down me-2"></i>SELL SIGNAL: Price moderately above MA';
                    signalClass = 'alert-warning';
                } else if (currentPrice > movingAverage + 10) {
                    signalText = '<i class="fas fa-arrow-down me-2"></i>STRONG SELL SIGNAL: Price significantly above MA';
                    signalClass = 'alert-danger';
                } else {
                    signalText = '<i class="fas fa-pause me-2"></i>HOLD: No clear signal';
                    signalClass = 'alert-info';
                }
                
                signalElement.innerHTML = signalText;
                signalElement.classList.add(signalClass);
            }
        })
        .catch(error => {
            console.error('Error updating moving average analysis:', error);
        });
}

// Function to toggle the trading bot
function toggleTradingBot() {
    const newState = !botEnabled;
    
    fetch('/api/toggle_bot', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        },
        body: JSON.stringify({ enabled: newState })
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            botEnabled = data.status;
            updateBotStatusUI();
        } else {
            console.error('Error toggling bot:', data.error);
            alert('Error toggling bot: ' + data.error);
        }
    })
    .catch(error => {
        console.error('Error toggling bot:', error);
        alert('Error toggling bot. See console for details.');
    });
}

// Function to update the bot status UI
function updateBotStatusUI() {
    const toggleBtn = document.getElementById('toggleBotBtn');
    const statusText = document.getElementById('botStatusText');
    
    if (botEnabled) {
        toggleBtn.className = 'btn btn-lg btn-success';
        toggleBtn.innerHTML = '<i class="fas fa-robot me-2"></i><span id="botStatusText">Trading Bot Active</span>';
    } else {
        toggleBtn.className = 'btn btn-lg btn-danger';
        toggleBtn.innerHTML = '<i class="fas fa-robot me-2"></i><span id="botStatusText">Enable Trading Bot</span>';
    }
}

// Function to check the bot status
function checkBotStatus() {
    fetch('/api/bot_status')
        .then(response => response.json())
        .then(data => {
            botEnabled = data.enabled;
            updateBotStatusUI();
            
            // Update API status indicators
            updateApiStatusDisplay(data);
        })
        .catch(error => {
            console.error('Error checking bot status:', error);
            
            // Show error state in the UI
            document.getElementById('apiStatusBadge').className = 'badge bg-danger';
            document.getElementById('apiStatusBadge').textContent = 'Error';
            document.getElementById('apiSourceBadge').className = 'badge bg-secondary';
            document.getElementById('apiSourceBadge').textContent = 'Unknown';
        });
}

// Function to update API status display
function updateApiStatusDisplay(data) {
    // Update API status badge
    const statusBadge = document.getElementById('apiStatusBadge');
    const sourceBadge = document.getElementById('apiSourceBadge');
    const cooldownInfo = document.getElementById('apiCooldownInfo');
    const cooldownUntil = document.getElementById('cooldownUntil');
    
    // Update source
    sourceBadge.textContent = data.api_source === 'coingecko' ? 'CoinGecko' : 'Binance';
    
    // Update status with appropriate color
    switch(data.api_status) {
        case 'online':
            statusBadge.className = 'badge bg-success';
            statusBadge.textContent = 'Online';
            cooldownInfo.style.display = 'none';
            break;
        case 'cooldown':
            statusBadge.className = 'badge bg-warning';
            statusBadge.textContent = 'Rate Limited';
            
            // Show cooldown info
            if (data.cooldown_until) {
                // Add timezone offset if missing
                let cooldownTimestamp = data.cooldown_until;
                if (!cooldownTimestamp.includes('+') && !cooldownTimestamp.includes('Z')) {
                    // Add local timezone offset for browser time
                    const localOffset = -(new Date().getTimezoneOffset());
                    const offsetHours = Math.floor(Math.abs(localOffset) / 60);
                    const offsetMinutes = Math.abs(localOffset) % 60;
                    const offsetSign = localOffset >= 0 ? '+' : '-';
                    const offsetString = `${offsetSign}${String(offsetHours).padStart(2, '0')}:${String(offsetMinutes).padStart(2, '0')}`;
                    cooldownTimestamp += offsetString;
                }
                
                const cooldownTime = new Date(cooldownTimestamp);
                cooldownUntil.textContent = cooldownTime.toLocaleTimeString(undefined, { 
                    hour: '2-digit', 
                    minute: '2-digit',
                    hour12: false,
                    timeZoneName: 'short'
                });
                cooldownInfo.style.display = 'block';
            }
            break;
        case 'error':
            statusBadge.className = 'badge bg-danger';
            statusBadge.textContent = 'Error';
            cooldownInfo.style.display = 'none';
            break;
        default:
            statusBadge.className = 'badge bg-secondary';
            statusBadge.textContent = 'Unknown';
            cooldownInfo.style.display = 'none';
    }
}

// Initialize everything when the DOM is loaded
document.addEventListener('DOMContentLoaded', function() {
    // Refresh data initially
    refreshPrice();
    refreshPortfolio();
    getRecentTrades();
    updateBotSettings();
    checkBotStatus();
    
    // Set up automatic refresh intervals
    setInterval(refreshPrice, PRICE_UPDATE_INTERVAL);
    setInterval(refreshPortfolio, PORTFOLIO_UPDATE_INTERVAL);
    setInterval(getRecentTrades, TRADE_HISTORY_UPDATE_INTERVAL);
    setInterval(checkBotStatus, BOT_STATUS_UPDATE_INTERVAL);
    
    // Set up event listeners
    document.getElementById('refreshPrice').addEventListener('click', refreshPrice);
    
    // Buy form submission
    document.getElementById('buyForm').addEventListener('submit', function(e) {
        e.preventDefault();
        
        const amount = parseFloat(document.getElementById('buyAmount').value);
        if (isNaN(amount) || amount <= 0) {
            alert('Please enter a valid amount');
            return;
        }
        
        fetch('/api/execute_trade', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                type: 'buy',
                amount: amount
            })
        })
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                alert(data.message);
                document.getElementById('buyAmount').value = '';
                document.getElementById('estimatedBTC').value = '';
                
                // Refresh data
                refreshPortfolio();
                getRecentTrades();
            } else {
                alert('Error: ' + data.error);
            }
        })
        .catch(error => {
            console.error('Error executing trade:', error);
            alert('Error executing trade. See console for details.');
        });
    });
    
    // Sell form submission
    document.getElementById('sellForm').addEventListener('submit', function(e) {
        e.preventDefault();
        
        const amount = parseFloat(document.getElementById('sellAmount').value);
        if (isNaN(amount) || amount <= 0) {
            alert('Please enter a valid amount');
            return;
        }
        
        fetch('/api/execute_trade', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                type: 'sell',
                amount: amount
            })
        })
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                alert(data.message);
                document.getElementById('sellAmount').value = '';
                document.getElementById('estimatedSellBTC').value = '';
                
                // Refresh data
                refreshPortfolio();
                getRecentTrades();
            } else {
                alert('Error: ' + data.error);
            }
        })
        .catch(error => {
            console.error('Error executing trade:', error);
            alert('Error executing trade. See console for details.');
        });
    });
    
    // Update estimated BTC when amount changes
    document.getElementById('buyAmount').addEventListener('input', updateEstimatedBTC);
    document.getElementById('sellAmount').addEventListener('input', updateEstimatedBTC);
    
    // Toggle trading bot
    document.getElementById('toggleBotBtn').addEventListener('click', toggleTradingBot);
});



// 🧠 Portfolio-Daten vom Server laden und anzeigen
function updatePortfolio() {
  fetch("/portfolio_data")
    .then(res => res.json())
    .then(data => {
      if (data.error) {
        console.error("Fehler beim Laden der Portfolio-Daten:", data.error);
        return;
      }

      document.getElementById("btcBalance").innerText = data.btc.toFixed(6);
      document.getElementById("usdBalance").innerText = `$${data.usd.toFixed(2)}`;
      document.getElementById("portfolioValue").innerText = `$${data.total.toFixed(2)}`;

      document.getElementById("btcPercentage").style.width = `${data.btc_percent}%`;
      document.getElementById("usdPercentage").style.width = `${data.usd_percent}%`;

      document.getElementById("btcPercentage").innerText = `BTC ${data.btc_percent.toFixed(1)}%`;
      document.getElementById("usdPercentage").innerText = `USD ${data.usd_percent.toFixed(1)}%`;
    })
    .catch(err => {
      console.error("Fehler beim Laden der Portfolio-Daten:", err);
    });
}

// Beim Laden der Seite automatisch starten
document.addEventListener("DOMContentLoaded", () => {
  updatePortfolio();
});
