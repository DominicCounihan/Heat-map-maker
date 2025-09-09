This project is a Flask-based web application for uploading, storing, and visualizing geospatial health data. It generates interactive heatmaps with Folium to compare communities with and without water filters in Rwanda.
Workflow- 

Upload CSV (location data) and Excel (feature data) files through the web interface.

Data is stored in a local SQLite database.

A Folium heatmap is generated showing symptom intensity levels across locations.

The map includes circle markers, and interactive legend.

Requirements-
Python 3.12+

Required Packages

Flask, Flask-SQLAlchemy , pandas, numpy,folium ,openpyxl (for reading Excel files)

<img width="820" height="437" alt="Heatmap_final_report" src="https://github.com/user-attachments/assets/640d0c6c-6c71-4123-bb0e-97ae9dc0c8db" />

Example of heat map generated with this program
