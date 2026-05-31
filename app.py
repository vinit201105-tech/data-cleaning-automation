import os
import io
import pandas as pd
from flask import Flask, render_template, request, jsonify, send_file, session
from werkzeug.utils import secure_filename
import tempfile
import uuid

app = Flask(__name__)
app.secret_key = 'super_secret_key_for_session'  # In a real app, use a secure random key

# Directories for uploads and cleaned files
UPLOAD_FOLDER = os.path.join(tempfile.gettempdir(), 'uploads')
CLEANED_FOLDER = os.path.join(tempfile.gettempdir(), 'cleaned')
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(CLEANED_FOLDER, exist_ok=True)

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['CLEANED_FOLDER'] = CLEANED_FOLDER
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16 MB max

def get_file_stats(df):
    # Replace NaNs with None for valid JSON serialization
    df_safe = df.replace({pd.NA: None})
    import numpy as np
    df_safe = df_safe.replace({np.nan: None})
    return {
        'total_rows': len(df),
        'columns': list(df.columns),
        'data': df_safe.to_dict(orient='records')
    }

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/upload', methods=['POST'])
def upload_file():
    if 'file' not in request.files:
        return jsonify({'error': 'No file part'}), 400
    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': 'No selected file'}), 400
    
    if file and file.filename.endswith('.csv'):
        filename = secure_filename(file.filename)
        file_id = str(uuid.uuid4())
        save_name = f"{file_id}_{filename}"
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], save_name)
        file.save(filepath)
        
        try:
            df = pd.read_csv(filepath)
            session['current_file'] = filepath
            session['file_id'] = file_id
            session['original_filename'] = filename
            
            stats = get_file_stats(df)
            return jsonify({'message': 'File uploaded successfully', 'stats': stats})
        except Exception as e:
            return jsonify({'error': str(e)}), 500
    
    return jsonify({'error': 'Invalid file format. Please upload a CSV.'}), 400

@app.route('/load-sample', methods=['POST'])
def load_sample():
    sample_path = os.path.join(os.path.dirname(__file__), 'sample_data.csv')
    if not os.path.exists(sample_path):
         return jsonify({'error': 'Sample data not found'}), 404
         
    file_id = str(uuid.uuid4())
    session['current_file'] = sample_path
    session['file_id'] = file_id
    session['original_filename'] = 'sample_data.csv'
    
    try:
        df = pd.read_csv(sample_path)
        stats = get_file_stats(df)
        return jsonify({'message': 'Sample data loaded successfully', 'stats': stats})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/clean', methods=['POST'])
def clean_data():
    if 'current_file' not in session:
        return jsonify({'error': 'No data loaded to clean'}), 400
        
    filepath = session['current_file']
    if not os.path.exists(filepath):
        return jsonify({'error': 'Data file not found'}), 404
        
    try:
        df = pd.read_csv(filepath)
        original_rows = len(df)
        # Convert whitespace-only strings to NaN
        df.replace(r'^\s*$', pd.NA, regex=True, inplace=True)
        
        # Ensure numeric columns are properly cast before filling missing values
        for col in df.columns:
            df[col] = pd.to_numeric(df[col], errors='ignore')
            
        original_missing = df.isnull().sum().sum()
        
        # 1. Remove duplicate rows
        df.drop_duplicates(inplace=True)
        duplicates_removed = original_rows - len(df)
        
        # 2. Fill missing numeric values with average
        numeric_cols = df.select_dtypes(include=['number']).columns
        missing_filled = 0
        for col in numeric_cols:
            missing_count = df[col].isnull().sum()
            if missing_count > 0:
                mean_val = df[col].mean()
                df[col] = df[col].fillna(mean_val)
                missing_filled += missing_count
                
        # 3. Remove extra spaces from text fields
        text_cols = df.select_dtypes(include=['object']).columns
        for col in text_cols:
            df[col] = df[col].apply(lambda x: x.strip() if isinstance(x, str) else x)
            
        # 4. Standardize column names
        df.columns = df.columns.str.strip().str.lower().str.replace(' ', '_')
        
        # Save cleaned file
        cleaned_filename = f"cleaned_{session.get('original_filename', 'data.csv')}"
        cleaned_filepath = os.path.join(app.config['CLEANED_FOLDER'], f"{session['file_id']}_{cleaned_filename}")
        df.to_csv(cleaned_filepath, index=False)
        session['cleaned_file'] = cleaned_filepath
        
        after_stats = get_file_stats(df)
        
        return jsonify({
            'message': 'Data cleaned successfully',
            'stats': after_stats,
            'cleaning_summary': {
                'original_rows': int(original_rows),
                'final_rows': int(len(df)),
                'duplicates_removed': int(duplicates_removed),
                'missing_values_fixed': int(missing_filled)
            }
        })
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

@app.route('/report', methods=['GET'])
def generate_report():
    if 'cleaned_file' not in session:
         return jsonify({'error': 'Please clean the data first before generating a report'}), 400
         
    cleaned_filepath = session['cleaned_file']
    if not os.path.exists(cleaned_filepath):
        return jsonify({'error': 'Cleaned data file not found'}), 404
        
    try:
        df = pd.read_csv(cleaned_filepath)
        
        # Summary statistics
        numeric_df = df.select_dtypes(include=['number'])
        summary_stats = numeric_df.describe().to_dict()
        
        # Data for Bar Chart: Sum of a numeric column by a categorical column
        # Try to find a categorical column and a numeric column
        cat_cols = df.select_dtypes(include=['object']).columns
        num_cols = df.select_dtypes(include=['number']).columns
        
        bar_chart_data = None
        pie_chart_data = None
        
        if len(cat_cols) > 0 and len(num_cols) > 0:
            # Let's use the first categorical and first numeric column for bar chart
            primary_cat = cat_cols[0]
            primary_num = num_cols[0]
            # Find the best columns if it's the sample sales data
            if 'category' in df.columns and 'sales' in df.columns:
                primary_cat = 'category'
                primary_num = 'sales'
            
            bar_df = df.groupby(primary_cat)[primary_num].sum().reset_index()
            bar_chart_data = {
                'labels': bar_df[primary_cat].tolist(),
                'values': bar_df[primary_num].tolist(),
                'label': f'Total {primary_num.title()} by {primary_cat.title()}'
            }
            
            # Pie Chart Data: Count of items in a categorical column
            pie_df = df[primary_cat].value_counts().reset_index()
            pie_chart_data = {
                 'labels': pie_df[primary_cat].tolist(),
                 'values': pie_df['count'].tolist(),
                 'label': f'Distribution of {primary_cat.title()}'
            }
            
        report_data = {
            'total_records': len(df),
            'summary': summary_stats,
            'top_records': df.head(5).to_dict(orient='records'),
            'columns': list(df.columns),
            'bar_chart': bar_chart_data,
            'pie_chart': pie_chart_data
        }
        
        return jsonify({'message': 'Report generated successfully', 'report': report_data})
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/download/cleaned', methods=['GET'])
def download_cleaned():
    if 'cleaned_file' not in session or not os.path.exists(session['cleaned_file']):
        return "Cleaned file not found", 404
        
    filename = f"cleaned_{session.get('original_filename', 'data.csv')}"
    return send_file(session['cleaned_file'], as_attachment=True, download_name=filename)

@app.route('/download/report', methods=['GET'])
def download_report():
    if 'cleaned_file' not in session or not os.path.exists(session['cleaned_file']):
         return "Cleaned data required to generate report", 404
         
    df = pd.read_csv(session['cleaned_file'])
    
    # Generate a simple text report
    report_text = f"Data Cleaning & Reporting Automation - Summary Report\n"
    report_text += "="*60 + "\n\n"
    report_text += f"Total Records: {len(df)}\n"
    report_text += f"Total Columns: {len(df.columns)}\n\n"
    
    report_text += "--- Columns ---\n"
    report_text += ", ".join(df.columns) + "\n\n"
    
    report_text += "--- Summary Statistics (Numeric Columns) ---\n"
    numeric_df = df.select_dtypes(include=['number'])
    if not numeric_df.empty:
        report_text += numeric_df.describe().to_string() + "\n\n"
    else:
        report_text += "No numeric columns found.\n\n"
        
    report_text += "--- Top 5 Records ---\n"
    report_text += df.head(5).to_string() + "\n"
    
    # Create in-memory file
    mem_file = io.BytesIO()
    mem_file.write(report_text.encode('utf-8'))
    mem_file.seek(0)
    
    report_filename = f"report_{session.get('original_filename', 'data').replace('.csv', '')}.txt"
    return send_file(mem_file, as_attachment=True, download_name=report_filename, mimetype='text/plain')

if __name__ == '__main__':
    app.run(debug=True, port=5000)
