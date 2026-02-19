import pandas as pd
try:
    import plotly.express as px
except Exception as e:
    print('PLOTLY_IMPORT_ERROR:', e)
    raise

df = pd.DataFrame({'iso3': ['USA', 'FRA', 'GBR'], 'num': [10, 5, 7]})

try:
    fig = px.choropleth_mapbox(
        df,
        locations='iso3',
        color='num',
        hover_name='iso3',
        mapbox_style='open-street-map',
        center={'lat': 20, 'lon': 0},
        zoom=1,
        title='Test Choropleth Mapbox'
    )
    fig.write_html('_test_choropleth_mapbox.html')
    print('OK: wrote _test_choropleth_mapbox.html')
except Exception as e:
    print('ERROR_CREATING_FIG:', e)
    raise
