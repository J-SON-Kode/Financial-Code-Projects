import streamlit as st
import numpy as np
import pandas as pd
import numpy_financial as nf
import altair as alt
from streamlit_echarts import st_echarts


st.set_page_config(layout="wide")
st.title("Property Investment Dashboard (Pure Rental ROI + Capital Gains)")

# --- Inputs ---
st.sidebar.header("Assumptions & Inputs")

purchase_price = st.sidebar.number_input(
    "Purchase Price (ZAR)",
    min_value=100_000,
    value=1_000_000,
    step=50_000,
    format="%d"  # optional currency‑style formatting
)

deposit = st.sidebar.slider(
    "Initial Deposit (ZAR)",
    min_value=0,
    max_value=purchase_price,      # keep deposit ≤ price
    value=200_000,
    step=10_000,
    format="R %d"
)

purchase_fees = st.sidebar.number_input(
    "Upfront Property Fees (ZAR)",
    value=50_000,
    step=5_000,
    min_value=0,
    format="%d"
)

loan_amount = purchase_price - deposit
st.sidebar.markdown(f"**Loan Amount (ZAR):** {loan_amount:,.0f}")

annual_interest = st.sidebar.slider(
    "Mortgage Interest Rate (%)",
    min_value=0.0,
    max_value=20.0,
    value=10.0,
    step=0.1
)

term_years = st.sidebar.slider(
    "Loan Term (Years)",
    min_value=1,
    max_value=30,
    value=20,
    step=1
)

monthly_rent = st.sidebar.number_input(
    "Starting Monthly Rent (ZAR)",
    value=15_000,
    step=500,
    min_value=0,
    format="%d"  # optional — suppresses decimals
)

monthly_costs = st.sidebar.number_input(
    "Monthly Rates & Levies (ZAR)",
    value=5_000,
    step=500,
    min_value=0,
    format="%d"
)

rental_escalation = st.sidebar.slider(
    "Annual Rent Escalation (%)",
    min_value=0.0,
    max_value=15.0,
    value=5.0,
    step=0.1
)

costs_escalation = st.sidebar.slider(
    "Annual Costs Escalation (%)",
    min_value=0.0,
    max_value=15.0,
    value=3.0,
    step=0.1
)

capital_growth = st.sidebar.slider(
    "Annual Property Appreciation (%)",
    min_value=0.0,
    max_value=15.0,
    value=4.0,
    step=0.1
)

# --- Validation ---
if purchase_price <= 0:
    st.error("Purchase price must be greater than 0.")
    st.stop()
if loan_amount <= 0:
    st.error("Deposit must be less than the purchase price.")
    st.stop()
if term_years <= 0:
    st.error("Loan term must be at least 1 year.")
    st.stop()

# --- Setup ---
monthly_rate = annual_interest / 100 / 12
n_periods = int(term_years * 12)
contract_payment = -nf.pmt(monthly_rate, n_periods, loan_amount)

# Trackers
initial_deposit = deposit + purchase_fees  # ⬅️ total upfront cash outlay
cumulative_cash_invested = initial_deposit  # deposit + any principal from cash
cumulative_principal_rent = 0       # principal funded by rent
total_interest_cash = 0             # interest paid out-of-pocket
balance = loan_amount
records = []

for m in range(1, n_periods + 1):
    years_elapsed = (m - 1) // 12
    rent_m = monthly_rent * (1 + rental_escalation / 100) ** years_elapsed
    cost_m = monthly_costs * (1 + costs_escalation / 100) ** years_elapsed
    net_rent = rent_m - cost_m

    if balance <= 0:
        # After payoff: all net rent is principal from rent
        base_payment = 0
        extra_payment = net_rent
        total_payment = net_rent
        interest_paid = 0
        interest_from_cash = 0
        interest_from_rent = 0
        principal_from_cash = 0
        principal_from_rent = net_rent
        balance = 0
        cumulative_principal_rent += principal_from_rent
    else:
        # Standard payment with access bond logic
        interest_amt = balance * monthly_rate
        base_payment = max(contract_payment, interest_amt)
        extra_payment = max(net_rent - base_payment, 0)
        total_payment = min(base_payment + extra_payment, balance + interest_amt)

        # Allocate payment
        interest_paid = min(total_payment, interest_amt)
        interest_from_cash = max(interest_paid - net_rent, 0)
        interest_from_rent = interest_paid - interest_from_cash
        principal_paid = total_payment - interest_paid
        principal_from_cash = max(principal_paid - principal_from_rent if False else max(principal_paid - max(net_rent - interest_paid, 0), 0), 0)
        principal_from_rent = principal_paid - principal_from_cash

        # Update balance and trackers
        balance -= principal_paid
        cumulative_cash_invested += principal_from_cash
        total_interest_cash += interest_from_cash
        cumulative_principal_rent += principal_from_rent

    # Equity after rent contributions and cash interest
    equity = initial_deposit + cumulative_principal_rent - total_interest_cash
    gain_from_rent = equity - initial_deposit
    roi_from_rent = (gain_from_rent / cumulative_cash_invested * 100) if cumulative_cash_invested > 0 else 0

    # Capital gain
    prop_value = purchase_price * (1 + capital_growth / 100) ** (m / 12)
    capital_gain = prop_value - purchase_price
    roi_from_capital = (capital_gain / cumulative_cash_invested * 100) if cumulative_cash_invested > 0 else 0

    # Total return and ROI
    total_return = gain_from_rent + capital_gain
    total_roi = (total_return / cumulative_cash_invested * 100) if cumulative_cash_invested > 0 else 0

    # Record
    records.append({
        'Month': m,
        'Year': years_elapsed + 1,
        'Rent (ZAR)': rent_m,
        'Costs (ZAR)': cost_m,
        'Net Rental': net_rent,
        'Mortgage Payment': total_payment,
        'Base Payment': base_payment,
        'Extra Payment': extra_payment,
        'Interest Paid': interest_paid,
        'Interest from Rent': interest_from_rent,
        'Interest from Cash': interest_from_cash,
        'Principal from Rent': principal_from_rent,
        'Principal from Cash': principal_from_cash,
        'Loan Balance': balance,
        'Equity': equity,
        'Gain From Rent': gain_from_rent,
        'ROI From Rent (%)': roi_from_rent,
        'Property Value': prop_value,
        'Capital Gain': capital_gain,
        'ROI From Capital (%)': roi_from_capital,
        'Total Return': total_return,
        'Total ROI (%)': total_roi,
        'Total Cash Invested': cumulative_cash_invested
    })

# Build DataFrame and display
df = pd.DataFrame(records)

st.header("Pure Rental Income ROI and Capital Gain Breakdown")
st.dataframe(df.style.format({
    'Rent (ZAR)': 'R {:,.0f}',
    'Costs (ZAR)': 'R {:,.0f}',
    'Net Rental': 'R {:,.0f}',
    'Mortgage Payment': 'R {:,.0f}',
    'Base Payment': 'R {:,.0f}',
    'Extra Payment': 'R {:,.0f}',
    'Interest Paid': 'R {:,.0f}',
    'Interest from Rent': 'R {:,.0f}',
    'Interest from Cash': 'R {:,.0f}',
    'Principal from Rent': 'R {:,.0f}',
    'Principal from Cash': 'R {:,.0f}',
    'Loan Balance': 'R {:,.0f}',
    'Equity': 'R {:,.0f}',
    'Gain From Rent': 'R {:,.0f}',
    'ROI From Rent (%)': '{:.2f}',
    'Property Value': 'R {:,.0f}',
    'Capital Gain': 'R {:,.0f}',
    'ROI From Capital (%)': '{:.2f}',
    'Total Return': 'R {:,.0f}',
    'Total ROI (%)': '{:.2f}',
    'Total Cash Invested': 'R {:,.0f}'
}))

# --Charting--

st.subheader("Return on Investment Over Time")

# Create 2 columns
col1, col2 = st.columns(2)

# ROI % Chart
with col1:
    st.markdown("**% Return Over Time**")
    roi_pct_df = df[['Month', 'ROI From Rent (%)', 'ROI From Capital (%)', 'Total ROI (%)']].set_index('Month')
    st.line_chart(roi_pct_df)

# ROI Rands Chart
with col2:
    st.markdown("**Rand Return Over Time**")
    roi_r_df = df[['Month', 'Gain From Rent', 'Capital Gain', 'Total Return']].set_index('Month')
    st.line_chart(roi_r_df)