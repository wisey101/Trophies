import streamlit as st
import pandas as pd
from st_supabase_connection import SupabaseConnection, execute_query
from supabase import create_client, Client
from io import BytesIO
import time

# Set page configuration
st.set_page_config(page_title="CRM Dashboard", layout="wide")

# Initialize Supabase connection
supabase = st.connection("supabase", type=SupabaseConnection)
supabase_url = st.secrets["connections"]["supabase"]["SUPABASE_URL"]
supabase_key = st.secrets["connections"]["supabase"]["SUPABASE_KEY"]

# Initialize Supabase client
supabase_client: Client = create_client(supabase_url, supabase_key)

# Page Title and Navigation
st.title("CRM Dashboard")
st.page_link("Trophy_manager.py", label="**Back to Trophy Manager**", icon="⬅️")

# Initialize session_state for upload tracking
if 'upload_complete' not in st.session_state:
    st.session_state['upload_complete'] = False

# Existing data fetching and dashboard code
@st.cache_data(ttl=600)
def get_merged_data():
    try:
        # Fetch data from 'website_orders'
        orders_response = execute_query(supabase.table("website_orders").select("*"), ttl=0)
        if not hasattr(orders_response, 'data') or not orders_response.data:
            st.error("No data found in 'website_orders' table.")
            return pd.DataFrame()
        orders_df = pd.DataFrame(orders_response.data)
        
        # Fetch data from 'website_codes_categories'
        categories_response = execute_query(supabase.table("website_codes_categories").select("*"), ttl=0)
        if not hasattr(categories_response, 'data') or not categories_response.data:
            st.error("No data found in 'website_codes_categories' table.")
            return pd.DataFrame()
        categories_df = pd.DataFrame(categories_response.data)
        
        # Perform left join on 'Code'
        merged_df = orders_df.merge(categories_df, on='Code', how='left')
        
        # Handle missing categories
        merged_df['Category'] = merged_df['Category'].fillna("Uncategorized")
        
        # Data Cleaning
        merged_df['Price'] = pd.to_numeric(merged_df['Price'], errors='coerce').fillna(0)
        merged_df['Quantity'] = pd.to_numeric(merged_df['Quantity'], errors='coerce').fillna(0).astype(int)
        merged_df['Order Date'] = pd.to_datetime(merged_df['Order Date'], errors='coerce')
        
        return merged_df
    except Exception as e:
        st.error(f"Error fetching data: {e}")
        return pd.DataFrame()

# Retrieve merged data
merged_df = get_merged_data()

# Check if data is available
if merged_df.empty:
    st.info("No order data available to display.")
    st.stop()

# Extract unique categories for the dropdown
categories = merged_df['Category'].dropna().unique().tolist()
categories.sort()

# Dropdown for category selection
selected_category = st.selectbox("Select a Category", options=["All Categories"] + categories)

# Filter data based on selected category
if selected_category and selected_category != "All Categories":
    category_df = merged_df[merged_df['Category'] == selected_category]
else:
    category_df = merged_df.copy()

# Check if there are orders in the selected category
if category_df.empty:
    st.warning("No orders found for the selected category.")
    st.stop()

# Ensure 'Order Date' is rounded to the nearest second to avoid duplicates due to milliseconds
category_df['Order Date'] = category_df['Order Date'].dt.round('s')

# Aggregate data by user
aggregated_df = category_df.groupby(['Email', 'First Name', 'Last Name']).agg(
    Total_Price_Spent=pd.NamedAgg(column='Price', aggfunc=lambda x: (x * category_df.loc[x.index, 'Quantity']).sum()),
    Quantity_Ordered=pd.NamedAgg(column='Quantity', aggfunc='sum'),
    Number_of_Orders=pd.NamedAgg(column='Order Date', aggfunc='nunique')  # Changed from 'ID' to 'Order Date'
).reset_index()

# Rename columns for better readability
aggregated_df.rename(columns={
    'Email': 'Email',
    'First Name': 'First Name',
    'Last Name': 'Last Name',
    'Total_Price_Spent': 'Total Price Spent (£)',
    'Quantity_Ordered': 'Total Quantity Ordered',
    'Number_of_Orders': 'Number of Orders'
}, inplace=True)

# Ensure 'Total Price Spent (£)' is numeric (float)
aggregated_df['Total Price Spent (£)'] = aggregated_df['Total Price Spent (£)'].astype(float)

# Display the aggregated data
st.subheader(f"Customer Orders for Category: {selected_category}" if selected_category != "All Categories" else "All Customer Orders")
st.dataframe(aggregated_df.style.format({
    'Total Price Spent (£)': '£{:,.2f}',
    'Total Quantity Ordered': '{:.0f}',
    'Number of Orders': '{:.0f}'
}))

# Optional: Download aggregated data as CSV
def convert_df_to_csv(df):
    return df.to_csv(index=False).encode('utf-8')

csv = convert_df_to_csv(aggregated_df)
st.download_button(
    label="📥 Download Data as CSV",
    data=csv,
    file_name='crm_customer_orders.csv',
    mime='text/csv',
)

# Optional: Add some basic metrics
st.markdown("---")
col1, col2, col3 = st.columns(3)

with col1:
    total_customers = aggregated_df.shape[0]
    st.metric("Total Customers", total_customers)

with col2:
    total_revenue = category_df['Price'].mul(category_df['Quantity']).sum()
    st.metric("Total Revenue (£)", f"£{total_revenue:,.2f}")

with col3:
    total_orders = category_df['Order Date'].nunique()  # Changed from 'ID' to 'Order Date'
    st.metric("Total Orders", total_orders)

# Optional: Visualizations
st.markdown("---")
st.subheader("Top 10 Customers by Revenue")

top_customers = aggregated_df.copy()
top_customers = top_customers.sort_values(by='Total Price Spent (£)', ascending=False).head(10)

st.bar_chart(data=top_customers.set_index('Email')['Total Price Spent (£)'])

# ------------------------
# New Feature: Upload and Insert Data
# ------------------------

st.sidebar.markdown("---")
st.sidebar.header("Upload Orders Data")

uploaded_file = None

if not st.session_state['upload_complete']:
    uploader_key = "file_uploader"
    uploaded_file = st.sidebar.file_uploader(
        "Upload your Excel file",
        type=["xlsx"],
        help="Ensure the Excel file has the correct columns as defined.",
        key=uploader_key
    )
else:
    st.sidebar.success("File uploaded and processed successfully.")
    if st.sidebar.button("Upload Another File"):
        st.session_state['upload_complete'] = False
        st.rerun()  # Refresh the app to reset the uploader

if uploaded_file is not None and not st.session_state['upload_complete']:
    try:
        # Read the Excel file into a pandas DataFrame
        df_upload = pd.read_excel(uploaded_file)

        # Define required columns based on your CSV definition
        required_columns = [
            "Order date",
            "Kód položky",
            "Name",
            "Cena/ks vč. DPH",
            "Počet ks",
            "Login",
            "Dodací příjmení",
            "Delivery address"
        ]

        # Check for missing columns
        missing_columns = [col for col in required_columns if col not in df_upload.columns]
        if missing_columns:
            st.error(f"The following required columns are missing: {', '.join(missing_columns)}")
            st.stop()

        # Existing Orders Extraction from merged_df
        existing_order_pairs = set(
            zip(
                merged_df['Order Date'].dt.strftime('%Y-%m-%dT%H:%M:%S'),
                merged_df['Code']
            )
        )
             
        # Mapping function (ID excluded and duplicate check added)
        def map_row_upload(row):
            
            try:
                # Convert 'Order date' to standardized string format
                order_date = pd.to_datetime(row["Order date"]).strftime('%Y-%m-%dT%H:%M:%S')
                code = row["Kód položky"]

                # Check if the (Order Date, Code) pair already exists
                if (order_date, code) in existing_order_pairs:
                    return None  # Skip this row
                
                if pd.isna(code):
                    return None

                # Prepare the data dictionary excluding ID
                return {
                    "Order Date": order_date,
                    "Code": code,
                    "Product Name": row["Name"],
                    "Price": float(str(row["Cena/ks vč. DPH"]).replace(',', '.')),
                    "Quantity": int(row["Počet ks"]),
                    "First Name": row["Login"],
                    "Last Name": row["Dodací příjmení"],
                    "Email": row["Delivery address"]
                }
            except Exception as e:
                st.warning(f"Error processing row with Order code {row.get('Order code', 'Unknown')}: {e}")
                return None

        # Apply mapping to all rows
        orders_to_insert = df_upload.apply(map_row_upload, axis=1).tolist()

        # Remove any rows that failed to process
        orders_to_insert = [order for order in orders_to_insert if order is not None]

        if not orders_to_insert:
            st.sidebar.error("No valid data to insert after processing.")
            st.stop()

        st.sidebar.success(f"Prepared {len(orders_to_insert)} rows for insertion.")

        # Insert data in batches to optimize performance
        batch_size = 100  # Adjust based on your needs

        if st.sidebar.button("Insert Uploaded Orders into Database"):
            total = len(orders_to_insert)
            inserted = 0
            failed = 0

            for i in range(0, total, batch_size):
                batch = orders_to_insert[i:i + batch_size]
                response = supabase_client.table("website_orders").insert(batch).execute()

                if response:
                    st.write(f"Batch {i//batch_size + 1} inserted successfully.")
                    inserted += len(batch)
                else:
                    st.error(f"Error inserting batch {i//batch_size + 1}: {response.json()}")
                    failed += len(batch)
                
                # Optional: Sleep to avoid rate limits
                time.sleep(0.5)
            
            st.success(f"Data insertion complete. Inserted: {inserted}, Failed: {failed}")

            st.session_state['upload_complete'] = True

            st.cache_data.clear() 
            st.rerun()

    except Exception as e:
        st.error(f"Error processing the uploaded file: {e}")
