/**
 * Config.js - Configuration page functionality for Bitcoin Trading Bot
 */

document.addEventListener('DOMContentLoaded', function() {
    // Handle reset button
    const resetButton = document.querySelector('button[type="reset"]');
    
    if (resetButton) {
        resetButton.addEventListener('click', function(e) {
            // Prevent the default form reset
            e.preventDefault();
            
            // Confirm reset
            if (confirm('Reset all settings to default values?')) {
                // Set default values
                document.getElementById('verkaufswert').value = '94500';
                document.getElementById('buying_percentage').value = '0.05';
                document.getElementById('selling_percentage_moderate').value = '0.25';
                document.getElementById('selling_percentage_high').value = '0.5';
                document.getElementById('ma_window').value = '3';
                document.getElementById('price_check_interval').value = '30';
            }
        });
    }
    
    // Form validation
    const configForm = document.querySelector('form');
    
    if (configForm) {
        configForm.addEventListener('submit', function(e) {
            let isValid = true;
            let errorMessage = '';
            
            // Validate verkaufswert
            const verkaufswert = parseFloat(document.getElementById('verkaufswert').value);
            if (isNaN(verkaufswert) || verkaufswert <= 0) {
                isValid = false;
                errorMessage += 'Sell threshold must be a positive number.\n';
            }
            
            // Validate buying percentage
            const buyingPercentage = parseFloat(document.getElementById('buying_percentage').value);
            if (isNaN(buyingPercentage) || buyingPercentage <= 0 || buyingPercentage > 1) {
                isValid = false;
                errorMessage += 'Buying percentage must be between 0.01 and 1.\n';
            }
            
            // Validate selling percentages
            const sellingPercentageModerate = parseFloat(document.getElementById('selling_percentage_moderate').value);
            if (isNaN(sellingPercentageModerate) || sellingPercentageModerate <= 0 || sellingPercentageModerate > 1) {
                isValid = false;
                errorMessage += 'Moderate selling percentage must be between 0.01 and 1.\n';
            }
            
            const sellingPercentageHigh = parseFloat(document.getElementById('selling_percentage_high').value);
            if (isNaN(sellingPercentageHigh) || sellingPercentageHigh <= 0 || sellingPercentageHigh > 1) {
                isValid = false;
                errorMessage += 'High selling percentage must be between 0.01 and 1.\n';
            }
            
            // Validate moving average window
            const maWindow = parseInt(document.getElementById('ma_window').value);
            if (isNaN(maWindow) || maWindow < 2 || maWindow > 10) {
                isValid = false;
                errorMessage += 'Moving average window must be between 2 and 10.\n';
            }
            
            // Validate price check interval
            const checkInterval = parseInt(document.getElementById('price_check_interval').value);
            if (isNaN(checkInterval) || checkInterval < 10 || checkInterval > 300) {
                isValid = false;
                errorMessage += 'Price check interval must be between 10 and 300 seconds.\n';
            }
            
            // Show error message if validation fails
            if (!isValid) {
                e.preventDefault();
                alert('Please fix the following errors:\n\n' + errorMessage);
            }
        });
    }
});
