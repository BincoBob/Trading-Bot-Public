/**
 * Charts.js - Chart initialization and data handling for Bitcoin Trading Bot
 */

// Create price chart with empty data (will be populated later)
let priceChart = null;

function initPriceChart() {
    const ctx = document.getElementById('priceChart').getContext('2d');
    
    // Verlauf für die Fläche unter der Kurve erstellen
    const gradient = ctx.createLinearGradient(0, 0, 0, 400);
    gradient.addColorStop(0, 'rgba(242, 169, 0, 0.5)');   // Oben: stärkeres Gold
    gradient.addColorStop(1, 'rgba(242, 169, 0, 0.05)');  // Unten: fast transparent
    
    priceChart = new Chart(ctx, {
        type: 'line',
        data: {
            labels: [],
            datasets: [{
                label: 'Bitcoin Price (USD)',
                data: [],
                borderColor: '#f2a900',  // Bitcoin gold
                backgroundColor: gradient,
                borderWidth: 3,
                tension: 0.3,  // Erhöhte Tension für glattere Kurven
                fill: true,
                pointRadius: 0,  // Keine Punkte für sauberere Darstellung
                pointHoverRadius: 6,  // Größere Hover-Punkte
                yAxisID: 'y'
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            animation: {
                duration: 1500,  // Längere Animation für schöneren Effekt
                easing: 'easeOutQuart'
            },
            interaction: {
                mode: 'nearest',
                axis: 'x',
                intersect: false
            },
            plugins: {
                tooltip: {
                    backgroundColor: 'rgba(0, 0, 0, 0.8)',
                    titleFont: {
                        size: 13,
                        weight: 'bold'
                    },
                    bodyFont: {
                        size: 12
                    },
                    padding: 12,
                    cornerRadius: 8,
                    displayColors: false,
                    callbacks: {
                        label: function(context) {
                            const label = context.dataset.label || '';
                            const value = context.raw;
                            
                            if (label.includes('Price')) {
                                return `Price: $${value.toLocaleString('en-US', { maximumFractionDigits: 2 })}`;
                            } else if (label.includes('Volume')) {
                                return `Volume: $${value.toLocaleString('en-US', { maximumFractionDigits: 0 })}`;
                            } else if (label.includes('Market Cap')) {
                                return `Market Cap: $${(value/1000000000).toLocaleString('en-US', { maximumFractionDigits: 2 })}B`;
                            }
                            return `${label}: ${value}`;
                        }
                    }
                },
                legend: {
                    display: true,
                    labels: {
                        usePointStyle: true,
                        padding: 15,
                        font: {
                            size: 12
                        }
                    }
                }
            },
            scales: {
                x: {
                    grid: {
                        display: false
                    },
                    ticks: {
                        maxTicksLimit: 8,
                        font: {
                            size: 10
                        },
                        color: 'rgba(120, 120, 120, 0.8)'
                    }
                },
                y: {
                    position: 'left',
                    grid: {
                        color: 'rgba(200, 200, 200, 0.08)'  // Hellere, subtilere Gitterlinien
                    },
                    border: {
                        dash: [4, 4]  // Gestrichelte Y-Achsenlinie
                    },
                    ticks: {
                        font: {
                            size: 11
                        },
                        padding: 8,
                        callback: function(value) {
                            return '$' + value.toLocaleString('en-US', { maximumFractionDigits: 0 });
                        }
                    },
                    beginAtZero: false
                },
                y1: {
                    position: 'right',
                    grid: {
                        display: false,
                    },
                    ticks: {
                        callback: function(value) {
                            return '$' + (value/1000000).toLocaleString('en-US', { maximumFractionDigits: 0 }) + 'M';
                        }
                    },
                    display: false  // Wird nur angezeigt, wenn Volumendaten vorhanden sind
                }
            }
        }
    });
}

// Function to update price chart with new data
function updatePriceChart(data) {
    // Format the data for the chart
    const labels = data.map(item => {
        // Parse the timestamp and apply local timezone (browser timezone)
        let dateString = item.timestamp;
        
        // Add timezone offset if missing (+02:00 for CEST, Europe/Berlin timezone)
        // This ensures timestamps without timezone info use browser's timezone
        if (!dateString.includes('+') && !dateString.includes('Z')) {
            // Add local timezone offset for browser time
            const localOffset = -(new Date().getTimezoneOffset());
            const offsetHours = Math.floor(Math.abs(localOffset) / 60);
            const offsetMinutes = Math.abs(localOffset) % 60;
            const offsetSign = localOffset >= 0 ? '+' : '-';
            const offsetString = `${offsetSign}${String(offsetHours).padStart(2, '0')}:${String(offsetMinutes).padStart(2, '0')}`;
            dateString += offsetString;
            
            console.log("Applying local timezone offset:", offsetString);
        }
        
        // Create date object (will be in local time)
        const date = new Date(dateString);
        
        // Enhanced formatting options for more readable time display
        const timeOptions = { 
            hour: '2-digit', 
            minute: '2-digit',
            hour12: false,  // 24-hour format
            timeZoneName: 'short'  // Add timezone indicator
        };
        
        const dateOptions = {
            day: '2-digit',
            month: '2-digit',
            year: 'numeric'  // Show year for clarity
        };
        
        // For longer periods, show full date
        if (data.length > 50) {
            return date.toLocaleDateString(undefined, dateOptions) + ' ' + 
                   date.toLocaleTimeString(undefined, timeOptions);
        } else {
            // For shorter periods, show time with timezone
            return date.toLocaleTimeString(undefined, timeOptions);
        }
    });
    
    const prices = data.map(item => item.price);
    
    // Update the chart
    priceChart.data.labels = labels;
    priceChart.data.datasets[0].data = prices;
    
    // Prüfen, ob Volumendaten vorhanden sind
    const hasVolume = data.some(item => item.volume);
    
    // Volumendaten hinzufügen, falls vorhanden
    if (hasVolume) {
        // Prüfen, ob bereits ein Dataset für das Volumen existiert
        let volumeDataset = priceChart.data.datasets.find(d => d.label === 'Trading Volume');
        
        if (!volumeDataset) {
            // Volume-Dataset erstellen, wenn noch nicht vorhanden
            volumeDataset = {
                label: 'Trading Volume',
                data: data.map(item => item.volume || 0),
                backgroundColor: 'rgba(153, 102, 255, 0.2)',
                borderColor: 'rgba(153, 102, 255, 0.8)',
                borderWidth: 1,
                type: 'bar',
                yAxisID: 'y1'
            };
            
            // Dataset hinzufügen
            priceChart.data.datasets.push(volumeDataset);
            
            // Y-Achse für Volumen aktivieren
            priceChart.options.scales.y1.display = true;
        } else {
            // Bestehende Volumendaten aktualisieren
            volumeDataset.data = data.map(item => item.volume || 0);
        }
    }
    
    // Marktkapitalisierung hinzufügen, falls vorhanden
    const hasMarketCap = data.some(item => item.marketCap);
    
    if (hasMarketCap) {
        // Prüfen, ob bereits ein Dataset für Market Cap existiert
        let marketCapDataset = priceChart.data.datasets.find(d => d.label === 'Market Cap');
        
        if (!marketCapDataset) {
            marketCapDataset = {
                label: 'Market Cap',
                data: data.map(item => item.marketCap || 0),
                borderColor: 'rgba(75, 192, 192, 1)',
                backgroundColor: 'rgba(75, 192, 192, 0)',
                borderWidth: 1,
                borderDash: [5, 5], // Gestrichelte Linie
                fill: false,
                type: 'line',
                pointRadius: 0,
                pointHoverRadius: 3,
                yAxisID: 'y1'
            };
            
            // Dataset hinzufügen
            priceChart.data.datasets.push(marketCapDataset);
            
            // Y-Achse für Market Cap aktivieren
            priceChart.options.scales.y1.display = true;
        } else {
            // Bestehende Market-Cap-Daten aktualisieren
            marketCapDataset.data = data.map(item => item.marketCap || 0);
        }
    }
    
    // Adjust options based on the amount of data
    if (data.length > 100) {
        priceChart.options.scales.x.ticks.maxTicksLimit = 15;
        priceChart.options.scales.x.ticks.autoSkip = true;
    } else {
        priceChart.options.scales.x.ticks.maxTicksLimit = 8;
    }
    
    priceChart.update();
    
    // Calculate price change
    if (prices.length >= 2) {
        const oldPrice = prices[0];
        const newPrice = prices[prices.length - 1];
        const change = newPrice - oldPrice;
        const percentChange = (change / oldPrice) * 100;
        
        // Update price change display
        const priceChangeElement = document.getElementById('priceChange');
        priceChangeElement.textContent = `${change >= 0 ? '+' : ''}${change.toFixed(2)} (${percentChange.toFixed(2)}%)`;
        priceChangeElement.className = `badge ${change >= 0 ? 'bg-success' : 'bg-danger'}`;
    }
}

// Load price history for the chart
function loadPriceHistory(days = 1) {
    // Request more data points for longer timeframes
    const limit = days > 7 ? 1000 : 500;
    
    // Automatisches Intervall wird vom Server bestimmt, aber kann überschrieben werden
    // z.B. 5 Minuten für Tagesansicht, 30 Minuten für Wochenansicht usw.
    const interval = 0; // 0 = automatisches Intervall basierend auf Zeitraum
    
    fetch(`/api/price_history?days=${days}&limit=${limit}&interval=${interval}`)
        .then(response => response.json())
        .then(data => {
            if (data.length > 0) {
                updatePriceChart(data);
                console.log(`Loaded ${data.length} price history data points for ${days} days`);
            } else {
                console.log('No price history data available');
            }
        })
        .catch(error => {
            console.error('Error fetching price history:', error);
        });
}

// Initialize charts when the DOM is loaded
document.addEventListener('DOMContentLoaded', function() {
    if (document.getElementById('priceChart')) {
        initPriceChart();
        loadPriceHistory(1);  // Load 1 day of history by default
        
        // Set up timeframe buttons
        const timeframeButtons = document.querySelectorAll('[data-timeframe]');
        timeframeButtons.forEach(button => {
            button.addEventListener('click', function() {
                // Remove active class from all buttons
                timeframeButtons.forEach(btn => btn.classList.remove('active'));
                // Add active class to clicked button
                this.classList.add('active');
                
                // Load data for selected timeframe
                const days = parseInt(this.getAttribute('data-timeframe'));
                loadPriceHistory(days);
            });
        });
    }
});
