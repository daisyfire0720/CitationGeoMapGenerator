from citation_map_generator import CitationMapGenerator, generate_citation_map
API_KEY = "aNPobAtZIsrciuiwkj12ov"   
MAILTO = "daisyfire0720@hotmail.com"    
TARGET_DOI = "10.1016/j.trd.2021.103159"

results = generate_citation_map(
        api_key=API_KEY,
        doi=TARGET_DOI,
        output_dir="./doi_output"
    )