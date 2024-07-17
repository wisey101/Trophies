import streamlit as st
import pandas as pd
import sqlite3

# Create or connect to the SQLite database
conn = sqlite3.connect('products.db')
cursor = conn.cursor()

# Drop the table if it exists (for debugging purposes, ensure the schema is correct)
cursor.execute('DROP TABLE IF EXISTS products')

# Create the products table with the correct schema
cursor.execute('''
    CREATE TABLE IF NOT EXISTS products (
        seller_sku TEXT PRIMARY KEY,
        asin TEXT,
        item_name TEXT,
        open_date TEXT,
        fulfillment_channel TEXT
    )
''')

def clean_column_names(df):
    df.columns = df.columns.str.strip()  # Strip any leading/trailing spaces
    return df

def load_txt(file):
    df = pd.read_csv(file, delimiter='\t')
    df = clean_column_names(df)
    
    for _, row in df.iterrows():
        cursor.execute('''
            INSERT OR REPLACE INTO products (seller_sku, asin, item_name, open_date, fulfillment_channel)
            VALUES (?, ?, ?, ?, ?)
        ''', (row['seller-sku'], row['asin1'], row['item-name'], row['open-date'], row['fulfillment-channel']))
    conn.commit()

def search_products(search_term, fulfillment_type):
    if fulfillment_type == "FBM":
        fulfillment_channel = "DEFAULT"
    else:
        fulfillment_channel = "AMAZON_EU"
    
    cursor.execute('''
        SELECT * FROM products
        WHERE LOWER(item_name) LIKE ? AND fulfillment_channel = ?
    ''', ('%' + search_term.lower() + '%', fulfillment_channel))
    results = cursor.fetchall()
    return pd.DataFrame(results, columns=['seller_sku', 'asin', 'item_name', 'open_date', 'fulfillment_channel'])

def update_excel_with_skus(filtered_df, template_excel_file):
    template_df = pd.read_excel(template_excel_file, sheet_name='Template')

    # Extract the first row (template) data except the SKU column
    template_row = template_df.iloc[0, 1:].values

    # Create new rows based on filtered SKUs
    new_rows = []
    for sku in filtered_df['seller_sku']:
        new_row = [sku] + list(template_row)
        new_rows.append(new_row)

    # Create a new DataFrame with updated data
    updated_df = pd.DataFrame(new_rows, columns=template_df.columns)

    # Export the updated DataFrame to a Unicode text file
    unicode_txt_path = 'bulk_customisation.txt'
    updated_df.to_csv(unicode_txt_path, sep='\t', index=False, encoding='utf-16')

    return unicode_txt_path

st.title("Product Search and Customization Application")

# File uploader for the template Excel file
template_file = st.file_uploader("Choose the template Excel file", type="xlsx")

# File uploader for the TXT file
uploaded_file = st.file_uploader("Choose a TXT file", type="txt")

if template_file and uploaded_file:
    load_txt(uploaded_file)
    st.success("TXT file loaded successfully!")

    # Search interface
    st.header("Search Products")
    search_term = st.text_input("Enter search term")
    fulfillment_type = st.radio("Select fulfillment type", ("FBM", "FBA"))

    if st.button("Search"):
        results = search_products(search_term, fulfillment_type)
        if not results.empty:
            st.write(f"Found {len(results)} results:")
            st.dataframe(results)
            
            # Create a download button for the results
            csv = results.to_csv(index=False)
            st.download_button(
                label="Download results as CSV",
                data=csv,
                file_name="search_results.csv",
                mime="text/csv"
            )

            # Update the Excel template with the filtered SKUs
            unicode_txt_path = update_excel_with_skus(results, template_file)

            # Create a download button for the Unicode text file
            with open(unicode_txt_path, 'rb') as f:
                st.download_button(
                    label="Download bulk_customisation.txt",
                    data=f,
                    file_name="bulk_customisation.txt",
                    mime="text/plain"
                )
        else:
            st.write("No results found.")
else:
    st.write("Please upload both the template Excel file and the TXT file to proceed.")

# Close the database connection when the application exits
conn.close()
