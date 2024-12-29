# US Equity Compensation for UK Workers: E*Trade Handler & CGT Calculator

Welcome to the **US Equity Compensation Fun for UK Workers** project. This tool is designed to simplify the complex world of RSUs (Restricted Stock Units), stock options, and capital gains tax (CGT) for UK taxpayers. Built with love (and frustration) over the bureaucratic maze of E*Trade reports and HMRC rules, this app consolidates your data into clear, actionable insights.

## 🎯 **What This App Does**
- **Connects fragmented E*Trade reports** into a single, consolidated view.
- **Handles UK tax rules** for RSUs, including:
  - Income tax at vest.
  - CGT calculations using HMRC Section 104 pooling rules.
  - Daily forex rates and accurate GBP conversions.
  - Adjustments for US holidays and non-business days.
- **Supports manual entries** for stock options and other transactions.
- **Generates detailed reports** for:
  - Consolidated transactions.
  - Validation logs.
  - CGT disposals.
  - Tax-year breakdown of gains/losses.

## 🚀 **How to Use**
1. **Prepare Your Files**
   - Download the required files from E*Trade:
     - `Gains/Losses Report`
     - `Benefits Report`
   - Collect additional required data:
     - `Stock Prices` (daily close values for your company's stock)
     - `Forex Rates` (GBP/USD daily average rates)
     - `US Holidays` (to adjust vesting dates)

2. **Upload Files**
   - Drag and drop or select your files in the respective sections.

3. **Add Manual Transactions (Optional)**
   - Use this feature to input additional transactions, such as exercised stock options.

4. **Process and Review**
   - Click the `Process Files` button.
   - Review:
     - Consolidated transaction data.
     - Validation report.
     - CGT disposals and gains/losses.

5. **Export Data**
   - Download reports as CSV files for further analysis or submission.

## 📦 **Features**
### **Data Consolidation**
- Combines data from multiple E*Trade reports into a single, cohesive output.

### **Automated Calculations**
- Calculates FMV (Fair Market Value) and GBP prices based on forex and stock data.
- Adjusts for UK tax-specific rules, including:
  - Same-day matching.
  - 30-day "Bed and Breakfasting" rules.
  - Section 104 pooling.

### **Validation**
- Highlights:
  - Missing FMV values.
  - Unmatched vest dates.
  - Negative or zero values in transactions.

### **Detailed Reporting**
- Outputs include:
  - Transaction history.
  - CGT summary by tax year.
  - Consolidated disposals with gain/loss calculations.

### **Local Processing**
- All data is processed client-side for security. No data is sent to external servers.

## 🛠️ **Setup & Requirements**
### **Prerequisites**
- A modern browser (e.g., Chrome, Edge, Firefox).
- Your E*Trade data files, along with stock prices, forex rates, and US holidays.

### **Optional Python Scripts**
- Use these scripts to fetch additional data:
  - `stock_price_downloader.py` (Fetch daily stock prices).
  - `gbpusdyahoo.py` (Fetch daily forex rates).
  - `holiday_downloader.py` (Fetch US holidays).

### **Hosted at**
[absolutelynotfinancialadvice.co.uk](https://www.absolutelynotfinancialadvice.co.uk)

### **Run Locally**
1. Clone the repository:
   ```bash
   git clone https://github.com/yourusername/rsu-cgt-calculator.git
   ```
2. Open `index.html` in your browser.

## 📖 **Documentation**
### **E*Trade Reports**
- **Gains/Losses Report**: Provides details of stock sales.
- **Benefits Report**: Contains vesting details.

### **Additional Data**
- **Stock Prices**: Historical daily close prices.
- **Forex Rates**: Daily average GBP/USD exchange rates.
- **US Holidays**: Adjust vest dates to the next valid business day.

### **UK Tax Rules Covered**
- **Income Tax**: Applied at vest based on FMV.
- **CGT Rules**:
  - Same-day rule.
  - Bed and breakfasting (30-day matching).
  - Section 104 pooling.

## 🎨 **Design Philosophy**
- **Cyberpunk Aesthetic**: A nod to the complexity and chaos of the financial system.
- **Transparency**: All data is processed client-side, ensuring user privacy.

## 📢 **Disclaimer**
- This tool is not financial or tax advice. Always consult a qualified professional.
- The app is provided "as is," without any warranty of accuracy or reliability.

## 🤝 **Contributing**
Contributions are welcome! Submit a pull request or raise an issue to discuss improvements or bug fixes.

## 💖 **Support This Project**
If you find this tool helpful, consider supporting its development by clicking the 'SUPPORT' button at :
- [absolutelynotfinancialadvice.co.uk](https://www.absolutelynotfinancialadvice.co.uk)

---
### **Acknowledgments**
- Inspired by the labyrinth of RSU taxation and E*Trade's fragmented data.
- Built for individuals trying to navigate the complex world of equity compensation.

---
### **License**
This software is licensed for personal, non-commercial use only. For commercial use, please contact the author. See LICENSE for more details.
