"""
Example: Citation Map Generator Usage

This script demonstrates different ways to use the citation_map_generator module.
"""

from citation_map_generator import CitationMapGenerator, generate_citation_map, generate_merged_citation_map


# ============================================================================
# Example 1: One-shot function (simplest approach)
# ============================================================================
def example_1_simple():
    """Generate everything in one call."""
    print("=" * 70)
    print("Example 1: Simple one-shot generation")
    print("=" * 70)
    
    api_key = "your_openalex_api_key_here"
    doi = "10.1016/j.apenergy.2022.119295"
    
    results = generate_citation_map(
        api_key=api_key,
        doi=doi,
        output_dir="./citations_output"
    )
    
    print(f"\nGenerated files:")
    print(f"  Map: {results['map_html']}")
    print(f"  Bar Chart: {results['bar_html']}")
    print(f"  Institution Pin Map: {results['institution_pin_map_html']}")
    print(f"  CSV Files: {results['citing_works']}, {results['country_counts']}, etc.")


# ============================================================================
# Example 2: Step-by-step (more control)
# ============================================================================
def example_2_steps():
    """Generate CSVs and visualizations separately."""
    print("\n" + "=" * 70)
    print("Example 2: Step-by-step with intermediate outputs")
    print("=" * 70)
    
    api_key = "your_openalex_api_key_here"
    doi = "10.1016/j.apenergy.2022.119295"
    output_dir = "./citations_output"
    
    # Create generator instance
    generator = CitationMapGenerator(api_key)
    
    # Step 1: Generate all intermediate CSV files
    print("\nStep 1: Generating CSVs...")
    csv_paths = generator.generate_csvs(doi, output_dir=output_dir)
    
    # You now have:
    #   - citing_works.csv: All papers citing the target
    #   - country_counts.csv: Citation counts by country
    #   - edges.csv: Network edges (for Gephi, etc.)
    #   - nodes.csv: Network nodes
    #   - institution_geo_counts.csv: Institution locations and citing paper counts
    
    # Step 2: Generate country-level visualizations with DOI in title
    print("\nStep 2: Generating country-level visualizations...")
    html_paths = generator.generate_html_visualizations(
        country_csv=csv_paths["country_counts"],
        doi=doi,
        output_dir=output_dir
    )
    
    print(f"\n✓ Country-level visualizations:")
    print(f"  - {html_paths['map_html']}")
    print(f"  - {html_paths['bar_html']}")
    
    # Step 3: Generate institution-level pin map with DOI in title
    print("\nStep 3: Generating institution pin map...")
    inst_maps = generator.generate_institution_pin_map(
        institution_csv=csv_paths["institution_geo"],
        doi=doi,
        output_dir=output_dir,
        top_n=120  # Limit to top 120 institutions for better performance
    )
    
    if inst_maps['institution_pin_map_html']:
        print(f"\n✓ Institution pin map:")
        print(f"  - {inst_maps['institution_pin_map_html']}")


# ============================================================================
# Example 3: With institution map limit (top N)
# ============================================================================
def example_3_with_institution_limit():
    """Generate all outputs with institution map limited to top N."""
    print("\n" + "=" * 70)
    print("Example 3: Full generation with limited institution map")
    print("=" * 70)
    
    api_key = "your_openalex_api_key_here"
    doi = "10.1016/j.apenergy.2022.119295"
    
    results = generate_citation_map(
        api_key=api_key,
        doi=doi,
        output_dir="./citations_output",
        top_n_institutions=100  # Show only top 100 institutions
    )
    
    print(f"\n✓ Generated {len([v for v in results.values() if v])} output files")


# ============================================================================
# Example 4: Process multiple DOIs
# ============================================================================
def example_4_multiple():
    """Generate citations for multiple papers."""
    print("\n" + "=" * 70)
    print("Example 4: Batch processing multiple DOIs")
    print("=" * 70)
    
    api_key = "your_openalex_api_key_here"
    output_base = "./batch_citations"
    
    dois = [
        "10.1016/j.apenergy.2022.119295",
        "10.1038/nature12373",
        "10.1126/science.1198493",
    ]
    
    for doi in dois:
        print(f"\n📝 Processing: {doi}")
        try:
            results = generate_citation_map(
                api_key=api_key,
                doi=doi,
                output_dir=f"{output_base}/{doi.replace('/', '_')}"
            )
        except Exception as e:
            print(f"  ❌ Error: {e}")


# ============================================================================
# Example 5: Custom analysis on generated CSVs
# ============================================================================
def example_5_custom_analysis():
    """Load CSVs and perform custom analysis."""
    print("\n" + "=" * 70)
    print("Example 5: Custom analysis on generated data")
    print("=" * 70)
    
    import pandas as pd
    
    # First generate the CSVs
    api_key = "your_openalex_api_key_here"
    doi = "10.1016/j.apenergy.2022.119295"
    
    generator = CitationMapGenerator(api_key)
    csv_paths = generator.generate_csvs(doi, output_dir="./output")
    
    # Now load and analyze
    citing_df = pd.read_csv(csv_paths["citing_works"])
    country_df = pd.read_csv(csv_paths["country_counts"])
    nodes_df = pd.read_csv(csv_paths["nodes"])
    edges_df = pd.read_csv(csv_paths["edges"])
    inst_geo_df = pd.read_csv(csv_paths["institution_geo"])
    
    print("\n📊 Custom Analysis:")
    print(f"  Total citing papers: {len(citing_df)}")
    print(f"  Countries represented: {len(country_df)}")
    print(f"  Most cited by: {country_df.iloc[0]['country_code']} ({country_df.iloc[0]['num_citing_papers']} papers)")
    print(f"  Average citations per citing paper: {citing_df['cited_by_count'].mean():.1f}")
    print(f"  Institutions with geo data: {len(inst_geo_df)}")
    print(f"  Top citing institution: {inst_geo_df.iloc[0]['institution_name']} ({inst_geo_df.iloc[0]['num_citing_papers']} papers)")
    
    # Example: Find top venues
    print("\n  Top citing venues:")
    top_venues = citing_df['citing_venue'].value_counts().head(5)
    for venue, count in top_venues.items():
        print(f"    - {venue}: {count} papers")
    
    # Example: Geographic analysis of institutions
    print("\n  Institution geographic distribution:")
    inst_by_country = inst_geo_df['country_code'].value_counts().head(5)
    for country, count in inst_by_country.items():
        print(f"    - {country}: {count} institutions")


# ============================================================================
# Example 6: Merge multiple DOI citations
# ============================================================================
def example_6_merge_citations():
    """Merge citation data from multiple DOIs into unified visualizations."""
    print("\n" + "=" * 70)
    print("Example 6: Merge citations from multiple papers")
    print("=" * 70)
    
    # First, generate individual citation data for each DOI
    api_key = "your_openalex_api_key_here"
    output_dir = "./doi_output"
    
    dois = [
        "10.1016/j.trd.2021.103159",
        "10.1016/j.apenergy.2022.119295",
        "10.1016/j.seta.2023.103267"
    ]
    
    print("\n📝 Step 1: Generate citation data for each DOI...")
    for doi in dois:
        print(f"  Processing: {doi}")
        try:
            results = generate_citation_map(
                api_key=api_key,
                doi=doi,
                output_dir=output_dir
            )
            print(f"    ✓ Generated")
        except Exception as e:
            print(f"    ❌ Error: {e}")
    
    print("\n🔗 Step 2: Merge all DOIs into unified visualizations...")
    try:
        merged_results = generate_merged_citation_map(
            doi_list=dois,
            output_dir=output_dir,
            top_n_institutions=None  # Show all institutions, or set to e.g. 50
        )
        
        print(f"\n✅ Merged files generated:")
        print(f"  Country Map: {merged_results['map_html']}")
        print(f"  Bar Chart: {merged_results['bar_html']}")
        print(f"  Institution Pin Map: {merged_results['institution_pin_map_html']}")
        print(f"  Merged CSVs: country_counts, institution_geo, citing_works, etc.")
    except Exception as e:
        print(f"  ❌ Error: {e}")


# ============================================================================
# Example 7: Using from command line
# ============================================================================
"""
You can also run citation_map_generator.py directly from the command line:

    # Generate with default DOI
    python citation_map_generator.py "your_api_key"
    
    # Specify DOI
    python citation_map_generator.py "your_api_key" "10.1016/j.apenergy.2022.119295"
    
    # Specify output directory
    python citation_map_generator.py "your_api_key" "10.1016/j.apenergy.2022.119295" "./my_output"
    
    # Limit institution map to top 100
    python citation_map_generator.py "your_api_key" "10.1016/j.apenergy.2022.119295" "./my_output" 100
"""


if __name__ == "__main__":
    # Choose which example to run by uncommenting:
    
    # example_1_simple()
    # example_2_steps()
    # example_3_with_institution_limit()
    # example_4_multiple()
    # example_5_custom_analysis()
    # example_6_merge_citations()
    
    print("Uncomment an example function in the __main__ section to run it!")
