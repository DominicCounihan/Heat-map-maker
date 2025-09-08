from io import BytesIO
from flask import Flask, render_template, request, send_file
from flask_sqlalchemy import SQLAlchemy
import folium
import pandas as pd
import numpy as np
from folium.plugins import HeatMap
import flask
import os

# Initialize flask and create sqlite database
app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///db.sqlite3'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

# Create datatable
class Upload(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    filename = db.Column(db.String(50))
    data = db.Column(db.LargeBinary)
    filetype = db.Column(db.String(10))  # 'csv' or 'excel'

# Create index function for upload and return files
@app.route('/', methods=['GET', 'POST'])
def index():
    if request.method == 'POST':
        files = request.files.getlist('files')
        for file in files:
            if file.filename != '':
                # Determine file type
                file_extension = file.filename.split('.')[-1].lower()
                filetype = 'excel' if file_extension in ['xlsx', 'xls'] else 'csv'
                
                upload = Upload(filename=file.filename, data=file.read(), filetype=filetype)
                db.session.add(upload)
        db.session.commit()
        return f'Uploaded {len(files)} files'
    return render_template('index.html')

# Create download function for download files
@app.route('/download/<upload_id>')
def download(upload_id):
    upload = Upload.query.filter_by(id=upload_id).first()
    return send_file(BytesIO(upload.data), 
                     download_name=upload.filename, as_attachment=True)

# Route to generate and display the heatmap
@app.route('/heatmap')
def generate_heatmap():
    # Get uploaded files
    csv_files = Upload.query.filter_by(filetype='csv').all()
    excel_files = Upload.query.filter_by(filetype='excel').all()
    
    if not csv_files or not excel_files:
        return "Please upload both CSV and Excel files first."
    
    # Use the latest CSV file for location data
    latest_csv = csv_files[-1]
    ld = pd.read_csv(BytesIO(latest_csv.data), names=['coord', 'name', 'value'])
    
    # Find Excel files (assuming naming convention)
    with_file = None
    without_file = None
    
    for excel_file in excel_files:
        if 'with' in excel_file.filename.lower():
            with_file = excel_file
        elif 'without' in excel_file.filename.lower():
            without_file = excel_file
    
    if not with_file or not without_file:
        return "Please upload both 'with' and 'without' Excel files."
    
    # Define column indices for data
    without_index = 18
    with_index = 31

    def load_values(file_data, num_points, index_data):
        value = []
        try:
            df = pd.read_excel(BytesIO(file_data), header=None)
            for a in range(7):
                values = df.iloc[1:, index_data + a].astype(float).values
                value.append(values)
            # Sum across all 7 columns
            summed_values = np.sum(value, axis=0)
            
            if len(summed_values) > 0:
                min_val, max_val = np.min(summed_values), np.max(summed_values)
                if max_val != min_val:
                    summed_values = ((summed_values - min_val) / (max_val - min_val)) * 100
                else:
                    summed_values = np.full_like(summed_values, 50)
            return summed_values
        except Exception as e:
            print(f"Error reading file: {e}")
            return np.zeros(num_points)

    def build_heat_data(ld, value_array):
        heat_data = []
        dropped_count = 0
        for index, row in ld.iterrows():
            coord_str = str(row['coord'])
            
            try:
                clean_str = coord_str.replace('POINT', '').replace('(', '').replace(')', '').replace('WKT', '').strip()
                coords = clean_str.split()
                if len(coords) >= 2:
                    lon, lat = float(coords[0]), float(coords[1])
                    intensity = value_array[index] if index < len(value_array) else 0
                    
                    if np.isnan(lat) or np.isnan(lon) or np.isnan(intensity):
                        dropped_count += 1
                        continue
                    
                    heat_data.append([lat, lon, intensity])
            except (ValueError, AttributeError) as e:
                dropped_count += 1
                print(f"Error processing coordinates at index {index}: {e}")
        print(f"Dropped {dropped_count} invalid rows.")
        return heat_data

    # Load and process data
    values_with = load_values(with_file.data, len(ld), with_index)
    heat_data_with = build_heat_data(ld, values_with)

    values_without = load_values(without_file.data, len(ld), without_index)
    heat_data_without = build_heat_data(ld, values_without)

    # Initialize map
    coordinates = [-1.9403, 29.8739]
    rwanda_map = folium.Map(location=coordinates, zoom_start=8, tiles='OpenStreetMap')

    # Create feature groups
    layer_with = folium.FeatureGroup(name="With Water Filter", show=True)
    layer_without = folium.FeatureGroup(name="Without Water Filter", show=False)

    # Add heatmaps
    if heat_data_with:
        HeatMap(
            heat_data_with,
            radius=15, blur=10, max_zoom=12, min_opacity=0.5, max_val=100,
            gradient={0.2: 'blue', 0.6: 'lime', 1: 'red'}
        ).add_to(layer_with)

    if heat_data_without:
        HeatMap(
            heat_data_without,
            radius=15, blur=10, max_zoom=12, min_opacity=0.5, max_val=100,
            gradient={0.2: 'blue', 0.6: 'lime', 1: 'red'}
        ).add_to(layer_without)
        
        # Add circle markers for the "without" layer
        for i, point in enumerate(heat_data_without):
            lat, lon, intensity = point
            name = str(ld.iloc[i]['name']).lower()

            # Black if contains both 'filter' and 'no', else white
            if 'filter' in name and 'no' in name:
                color = 'black'
            else:
                color = 'white'
                
            folium.CircleMarker(
                location=[lat, lon],
                radius=7,
                color=color,
                fill=True,
                fill_color=color,
                fill_opacity=0.7,
                popup=f"Name: {ld.iloc[i]['name']}<br>Intensity: {intensity:.1f}"
            ).add_to(layer_without)

    # Add layers to map
    layer_with.add_to(rwanda_map)
    layer_without.add_to(rwanda_map)

    # Add layer control
    folium.LayerControl(collapsed=False).add_to(rwanda_map)

    # Add title
    title_html = '''
    <h3 align="center" style="font-size:20px">
        <b> Heatmap</b>
    </h3>
    '''
    rwanda_map.get_root().html.add_child(folium.Element(title_html))

    # Add legend
    legend_html = '''
    <div style="
        position: fixed;
        bottom: 50px;
        left: 50px;
        width: 180px;
        height: 110px;
        background-color: white;
        border:2px solid grey;
        z-index:9999;
        font-size:14px;
        padding: 10px;
    ">
    <b>Heatmap Legend</b><br>
    <i style="background:blue; width:15px; height:15px; float:left; margin-right:10px; opacity:0.8;"></i>No symptoms<br>
    <i style="background:lime; width:15px; height:15px; float:left; margin-right:10px; opacity:0.8;"></i>Moderate symptoms<br>
    <i style="background:red; width:15px; height:15px; float:left; margin-right:10px; opacity:0.8;"></i>High symptoms
    </div>
    '''
    rwanda_map.get_root().html.add_child(folium.Element(legend_html))

    # Return the map as HTML
    return rwanda_map._repr_html_()

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True)
