"""
Citation Map Generator

A reusable module for generating citation analyses and visualizations from OpenAlex data.

Input:
  - API_KEY: OpenAlex API key for authenticated requests
  - TARGET_DOI: DOI of the target paper to analyze

Output:
  - CSV files: citing_works.csv, country_counts.csv, edges.csv, nodes.csv
  - HTML files: citation_country_map.html, citation_country_bar.html
"""

import time
import requests
import pandas as pd
from collections import Counter
from pathlib import Path
from typing import Dict, List, Set, Optional
import os


class CitationMapGenerator:
    """Generate citation networks and visualizations from OpenAlex API."""
    
    BASE_URL = "https://api.openalex.org"
    
    def __init__(self, api_key: str, mailto: Optional[str] = None):
        """
        Initialize the generator with API credentials.
        
        Args:
            api_key: OpenAlex API key
            mailto: Email address for API requests (recommended for rate limiting)
        """
        self.api_key = api_key
        self.mailto = mailto or "researcher@example.com"
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (citation-map; contact=mailto)"
        })
    
    def _get_json(self, url: str, params: Optional[Dict] = None, max_retries: int = 8, base_sleep: float = 0.6) -> Dict:
        """
        Robust GET request with retry logic and error handling.
        
        Retries on:
          - 429 (rate limiting)
          - 5xx errors
          - Non-JSON responses
        
        Args:
            url: Target URL
            params: Query parameters
            max_retries: Maximum retry attempts
            base_sleep: Base sleep duration for exponential backoff
            
        Returns:
            Parsed JSON response
            
        Raises:
            ValueError: If URL is empty
            RuntimeError: If all retries fail
        """
        if not url:
            raise ValueError("URL is empty/None")
        
        params = params.copy() if params else {}
        if self.api_key:
            params["api_key"] = self.api_key
        if self.mailto:
            params["mailto"] = self.mailto
        
        last_status = None
        last_text_head = None
        
        for i in range(max_retries):
            r = self.session.get(url, params=params, timeout=45)
            last_status = r.status_code
            text = r.text or ""
            last_text_head = text[:200].replace("\n", " ")
            
            # Success path: status 200 + valid JSON
            if r.status_code == 200:
                ctype = (r.headers.get("Content-Type") or "").lower()
                if "json" in ctype and text.strip():
                    try:
                        return r.json()
                    except Exception:
                        pass  # Retry on malformed JSON
            elif r.status_code in (429, 500, 502, 503, 504):
                pass  # Retry on these errors
            else:
                raise RuntimeError(
                    f"Request failed: {r.status_code}\nURL: {r.url}\nBody head: {last_text_head}"
                )
            
            # Exponential backoff
            sleep_s = (2 ** i) * base_sleep
            time.sleep(sleep_s)
        
        raise RuntimeError(
            f"Failed after retries. Last status={last_status}\nURL: {url}\nBody head: {last_text_head}"
        )
    
    def _to_api_work_url(self, openalex_id: str) -> str:
        """
        Convert OpenAlex work ID to API endpoint.
        
        Args:
            openalex_id: Can be a full URL or just the ID (e.g., W123)
            
        Returns:
            Full API endpoint URL
            
        Raises:
            ValueError: If ID is empty
        """
        if not openalex_id:
            raise ValueError("Empty OpenAlex ID")
        
        oid = openalex_id.strip()
        oid = oid.replace("https://openalex.org/", "")
        oid = oid.replace("http://openalex.org/", "")
        
        return f"{self.BASE_URL}/works/{oid}"
    
    def _to_api_inst_url(self, openalex_id: str) -> str:
        """
        Convert OpenAlex institution ID to API endpoint.
        
        Args:
            openalex_id: Can be a full URL or just the ID (e.g., I123)
            
        Returns:
            Full API endpoint URL
            
        Raises:
            ValueError: If ID is empty
        """
        if not openalex_id:
            raise ValueError("Empty OpenAlex institution ID")
        
        iid = openalex_id.strip()
        iid = iid.replace("https://openalex.org/", "")
        iid = iid.replace("http://openalex.org/", "")
        
        return f"{self.BASE_URL}/institutions/{iid}"
    
    def get_target_work(self, doi: str) -> Dict:
        """
        Fetch target work metadata by DOI.
        
        Args:
            doi: Paper DOI (with or without https://doi.org/ prefix)
            
        Returns:
            Work object with id, display_name, publication_year
            
        Raises:
            RuntimeError: If work not found
        """
        # Clean DOI
        doi = doi.replace("https://doi.org/", "").strip()
        
        url = f"{self.BASE_URL}/works/https://doi.org/{doi}"
        work = self._get_json(url)
        
        if not work.get("id"):
            raise RuntimeError(f"Failed to fetch work for DOI: {doi}. Check if DOI is correct.")
        
        return work
    
    def get_citing_works(self, target_openalex_id: str, per_page: int = 200) -> pd.DataFrame:
        """
        Fetch all papers that cite the target work.
        
        Uses cursor paging for stability.
        
        Args:
            target_openalex_id: OpenAlex ID of the target work (e.g., W12345...)
            per_page: Results per page (default 200)
            
        Returns:
            DataFrame with columns: citing_openalex_id, citing_title, citing_year, 
                                    citing_doi, citing_venue, cited_by_count
        """
        citing_rows = []
        cursor = "*"  # Start cursor for paging
        
        while True:
            url = f"{self.BASE_URL}/works"
            params = {
                "filter": f"cites:{target_openalex_id}",
                "per-page": per_page,
                "cursor": cursor,
                "select": "id,display_name,publication_year,doi,primary_location,cited_by_count"
            }
            data = self._get_json(url, params=params)
            results = data.get("results", [])
            
            if not results:
                break
            
            for w in results:
                citing_rows.append({
                    "citing_openalex_id": w.get("id"),
                    "citing_title": w.get("display_name"),
                    "citing_year": w.get("publication_year"),
                    "citing_doi": (w.get("doi") or "").replace("https://doi.org/", ""),
                    "citing_venue": (w.get("primary_location") or {}).get("source", {}).get("display_name"),
                    "cited_by_count": w.get("cited_by_count"),
                })
            
            cursor = data.get("meta", {}).get("next_cursor")
            if not cursor:
                break
            
            time.sleep(0.12)
        
        citing_df = pd.DataFrame(citing_rows).drop_duplicates(
            subset=["citing_openalex_id"]
        ).reset_index(drop=True)
        
        print(f"✓ Found {len(citing_df)} citing works")
        return citing_df
    
    def extract_country_codes(self, citing_df: pd.DataFrame) -> pd.DataFrame:
        """
        Extract country codes from author institutions in citing works.
        
        Args:
            citing_df: DataFrame from get_citing_works()
            
        Returns:
            Same DataFrame with added 'country_codes' column (semicolon-separated)
        """
        paper_to_countries = {}
        paper_country_list = []
        
        for idx, row in citing_df.iterrows():
            wid = row["citing_openalex_id"]
            if not wid:
                continue
            
            wobj = self._get_json(
                self._to_api_work_url(wid),
                params={"select": "id,authorships"}
            )
            
            countries = set()
            for auth in (wobj.get("authorships") or []):
                for inst in (auth.get("institutions") or []):
                    cc = inst.get("country_code")
                    if cc:
                        countries.add(cc)
            
            cc_sorted = sorted(countries)
            paper_to_countries[wid] = cc_sorted
            
            for cc in cc_sorted:
                paper_country_list.append(cc)
            
            if (idx + 1) % 20 == 0:
                print(f"  Processed {idx+1}/{len(citing_df)} papers...")
            
            time.sleep(0.05)
        
        citing_df["country_codes"] = citing_df["citing_openalex_id"].map(
            lambda x: ";".join(paper_to_countries.get(x, []))
        )
        
        print(f"✓ Extracted country codes for {len(citing_df)} papers")
        return citing_df, paper_country_list    
    def extract_institution_geo_data(self, citing_df: pd.DataFrame) -> pd.DataFrame:
        """
        Extract institution locations from citing works and count papers per institution.
        
        Creates a DataFrame with institution geo coordinates and the count of citing papers
        affiliated with each institution.
        
        Args:
            citing_df: DataFrame from get_citing_works()
            
        Returns:
            DataFrame with columns: institution_id, institution_name, country_code, city,
                                    latitude, longitude, num_citing_papers
        """
        from collections import defaultdict
        
        inst_to_papers = defaultdict(set)
        
        # First pass: collect all institutions from citing papers
        for i, row in citing_df.iterrows():
            wid = row["citing_openalex_id"]
            if not wid:
                continue
            
            wobj = self._get_json(
                self._to_api_work_url(wid),
                params={"select": "id,authorships"}
            )
            
            inst_ids = set()
            for auth in (wobj.get("authorships") or []):
                for inst in (auth.get("institutions") or []):
                    inst_id = inst.get("id")
                    if inst_id:
                        inst_ids.add(inst_id)
            
            for inst_id in inst_ids:
                inst_to_papers[inst_id].add(wid)
            
            if (i + 1) % 10 == 0:
                print(f"  Processed institutions for {i+1}/{len(citing_df)} citing papers...")
            
            time.sleep(0.05)
        
        # Second pass: fetch institution geo data
        inst_rows = []
        for j, (inst_id, paper_set) in enumerate(inst_to_papers.items(), start=1):
            inst_obj = self._get_json(
                self._to_api_inst_url(inst_id),
                params={"select": "id,display_name,country_code,geo"}
            )
            
            geo = inst_obj.get("geo") or {}
            lat = geo.get("latitude")
            lon = geo.get("longitude")
            city = geo.get("city")
            
            # Skip institutions without geo data
            if lat is None or lon is None:
                continue
            
            inst_rows.append({
                "institution_id": inst_obj.get("id"),
                "institution_name": inst_obj.get("display_name"),
                "country_code": inst_obj.get("country_code"),
                "city": city,
                "latitude": lat,
                "longitude": lon,
                "num_citing_papers": len(paper_set),
            })
            
            if j % 50 == 0:
                print(f"  Fetched geo for {j}/{len(inst_to_papers)} institutions...")
            
            time.sleep(0.05)
        
        inst_geo_df = pd.DataFrame(inst_rows).sort_values(
            "num_citing_papers", ascending=False
        ).reset_index(drop=True)
        
        print(f"✓ Extracted geo data for {len(inst_geo_df)} institutions")
        return inst_geo_df    
    def generate_csvs(self, doi: str, output_dir: Optional[str] = None) -> Dict[str, str]:
        """
        Generate intermediate CSV files for citation analysis.
        
        Args:
            doi: Target paper DOI
            output_dir: Output directory (default: current directory)
            
        Returns:
            Dictionary with keys: citing_works, country_counts, edges, nodes, institution_geo
            Values are file paths
        """
        output_dir = Path(output_dir or ".")
        output_dir.mkdir(parents=True, exist_ok=True)
        
        print(f"\n📊 Generating CSVs for DOI: {doi}")
        
        # Step 1: Get target work
        target_work = self.get_target_work(doi)
        target_id = target_work["id"]
        target_title = target_work.get("display_name", "Unknown")
        target_year = target_work.get("publication_year")
        
        print(f"  Target: {target_title} ({target_year})")
        
        # Step 2: Get citing works
        citing_df = self.get_citing_works(target_id)
        
        # Step 3: Extract country codes
        citing_df, country_list = self.extract_country_codes(citing_df)
        
        # Step 4: Create country counts
        country_counts = Counter(country_list)
        country_df = pd.DataFrame(
            country_counts.items(),
            columns=["country_code", "num_citing_papers"]
        ).sort_values("num_citing_papers", ascending=False).reset_index(drop=True)
        
        print(f"✓ Found {len(country_df)} countries")
        
        # Step 5: Create edges and nodes for network analysis
        edges_df = pd.DataFrame({
            "source": [target_id] * len(citing_df),
            "target": citing_df["citing_openalex_id"].tolist(),
            "type": ["Directed"] * len(citing_df)
        })
        
        nodes = [{
            "id": target_id,
            "label": target_title,
            "year": target_year,
            "country_codes": ""
        }]
        for _, r in citing_df.iterrows():
            nodes.append({
                "id": r["citing_openalex_id"],
                "label": r["citing_title"],
                "year": r["citing_year"],
                "country_codes": r["country_codes"]
            })
        nodes_df = pd.DataFrame(nodes).drop_duplicates(subset=["id"]).reset_index(drop=True)
        
        # Step 6: Extract institution geo data
        print("\n📍 Extracting institution geo data...")
        inst_geo_df = self.extract_institution_geo_data(citing_df)
        
        # Save files
        files = {
            "citing_works": output_dir / f"{doi.replace('/', '_')}_citing_works.csv",
            "country_counts": output_dir / f"{doi.replace('/', '_')}_country_counts.csv",
            "edges": output_dir / f"{doi.replace('/', '_')}_edges.csv",
            "nodes": output_dir / f"{doi.replace('/', '_')}_nodes.csv",
            "institution_geo": output_dir / f"{doi.replace('/', '_')}_institution_geo_counts.csv"
        }
        
        citing_df.to_csv(files["citing_works"], index=False)
        country_df.to_csv(files["country_counts"], index=False)
        edges_df.to_csv(files["edges"], index=False)
        nodes_df.to_csv(files["nodes"], index=False)
        inst_geo_df.to_csv(files["institution_geo"], index=False)
        
        print(f"\n✓ Saved CSV files to {output_dir}:")
        for key, path in files.items():
            print(f"  - {path.name}")
        
        return {k: str(v) for k, v in files.items()}
    
    def generate_html_visualizations(self, country_csv: str, doi: str = "", output_dir: Optional[str] = None) -> Dict[str, str]:
        """
        Generate HTML visualizations from country counts CSV.
        
        Args:
            country_csv: Path to country_counts.csv
            doi: Target paper DOI (for title)
            output_dir: Output directory (default: same as country_csv)
            
        Returns:
            Dictionary with keys: map_html, bar_html
            Values are file paths (as strings)
        """
        try:
            import plotly.express as px
        except ImportError:
            raise ImportError("Please install plotly: pip install -U plotly")
        
        try:
            import pycountry
        except ImportError:
            raise ImportError("Please install pycountry: pip install -U pycountry")
        
        output_dir = Path(output_dir or ".") if not output_dir else Path(output_dir)
        
        print(f"\n🗺️  Generating HTML visualizations from {country_csv}")
        
        # Load data
        country_df = pd.read_csv(country_csv)
        required_cols = {"country_code", "num_citing_papers"}
        missing = required_cols - set(country_df.columns)
        if missing:
            raise ValueError(f"country_counts.csv missing columns: {missing}")
        
        country_df["country_code"] = country_df["country_code"].astype(str).str.upper().str.strip()
        country_df["num_citing_papers"] = pd.to_numeric(
            country_df["num_citing_papers"], errors="coerce"
        ).fillna(0).astype(int)
        
        # Convert ISO2 to ISO3
        def iso2_to_iso3(iso2: str):
            iso2 = (iso2 or "").strip().upper()
            if not iso2:
                return None
            
            special = {"XK": "XKX"}  # Kosovo
            if iso2 in special:
                return special[iso2]
            
            c = pycountry.countries.get(alpha_2=iso2)
            return c.alpha_3 if c else None
        
        plot_df = country_df.copy()
        plot_df["iso3"] = plot_df["country_code"].apply(iso2_to_iso3)
        plot_df = plot_df.dropna(subset=["iso3"]).reset_index(drop=True)
        
        if plot_df.empty:
            raise RuntimeError("No countries could be mapped to ISO-3 codes.")
        
        # Build title with DOI
        doi_str = f" ({doi})" if doi else ""
        map_title = f"Global Citation Diffusion Map {doi_str}"
        bar_title = f"Top 20 Countries by Number of Citing Papers {doi_str}"
        
        # Create choropleth map using Mapbox style (open-street-map).
        # Explicitly set center/zoom and a more distinct color scale to avoid
        # low-contrast 'all-blue' outputs when values are similar.
        vmin = int(plot_df["num_citing_papers"].min())
        vmax = int(plot_df["num_citing_papers"].max())

        map_fig = px.choropleth(
                        plot_df,
                        locations="iso3",
                        color="num_citing_papers",
                        hover_name="country_code",
                        hover_data={"num_citing_papers": True},
                        labels={"num_citing_papers": "Number of Citing Papers"},
                        title=map_title,
                    )
        map_fig.update_layout(
                title=dict(
                    text=map_title,
                    x=0.5,
                    xanchor="center",
                    y=0.98,
                    yanchor="top",
                    font=dict(
                        size=22,
                        family="Arial, sans-serif"
                    )
                ),
                margin=dict(l=0, r=0, t=70, b=0),
            )
        map_fig.update_layout(
                    width=1200,
                    height=550, 
                    margin=dict(l=0, r=0, t=60, b=0),
                    title=dict(
                        x=0.5,
                        xanchor="center",
                        y=0.95,
                        yanchor="top"
                    ),
                    coloraxis_colorbar=dict(
                        title="Number of Citing Papers",
                        len=0.7,
                        y=0.5
                    ),
                    geo=dict(
                        projection_type="natural earth",
                        showcountries=True,
                        showcoastlines=True,
                        domain=dict(x=[0, 0.88], y=[0, 1]),
                        fitbounds="locations"
                    )
                )
        
        # Create bar chart
        TOP_N = 20
        bar_df = plot_df.sort_values("num_citing_papers", ascending=False).head(TOP_N)
        
        bar_fig = px.bar(
            bar_df,
            x="country_code",
            y="num_citing_papers",
            labels={"country_code": "Country", "num_citing_papers": "Number of Citing Papers"},
            title=bar_title
        )
        bar_fig.update_layout(
            margin=dict(l=20, r=20, t=70, b=20),
            xaxis_tickangle=-45
        )
        bar_fig.update_layout(
                title=dict(
                    text=bar_title,
                    x=0.5,
                    xanchor="center",
                    y=0.98,
                    yanchor="top",
                    font=dict(
                        size=16,
                        family="Arial, sans-serif"
                    )
                ),
                margin=dict(l=0, r=0, t=70, b=0),
            )
        
        # Save HTML files
        map_path = output_dir / f"{doi.replace('/', '_')}_citation_country_map.html"
        bar_path = output_dir / f"{doi.replace('/', '_')}_citation_country_bar.html"
        
        map_fig.write_html(str(map_path))
        bar_fig.write_html(str(bar_path))
        
        # Try to save PNG files (optional, requires kaleido)
        try:
            map_fig.write_image(str(output_dir / f"{doi.replace('/', '_')}_citation_country_map.png"), scale=2)
            bar_fig.write_image(str(output_dir / f"{doi.replace('/', '_')}_citation_country_bar.png"), scale=2)
            print(f"  - {doi.replace('/', '_')}_citation_country_map.png")
            print(f"  - {doi.replace('/', '_')}_citation_country_bar.png")
        except Exception as e:
            print(f"  PNG export skipped (optional). Install kaleido for PNG support: pip install -U kaleido")
        
        print(f"\n✓ Saved HTML visualizations:")
        print(f"  - {map_path.name}")
        print(f"  - {bar_path.name}")
        
        return {
            "map_html": str(map_path),
            "bar_html": str(bar_path)
        }
    
    def generate_institution_pin_map(self, institution_csv: str, doi: str = "", output_dir: Optional[str] = None, top_n: Optional[int] = None) -> Dict[str, str]:
        """
        Generate institution-level pin map visualization (scatter map on OpenStreetMap).
        
        Args:
            institution_csv: Path to institution_geo_counts.csv
            doi: Target paper DOI (for title)
            output_dir: Output directory (default: same as institution_csv)
            top_n: Limit to top N institutions by citing paper count (None = all)
            
        Returns:
            Dictionary with key: institution_pin_map_html
            Value is file path (as string)
        """
        try:
            import plotly.express as px
        except ImportError:
            raise ImportError("Please install plotly: pip install -U plotly")
        
        output_dir = Path(output_dir or ".") if not output_dir else Path(output_dir)
        
        print(f"\n📍 Generating institution pin map from {institution_csv}")
        
        # Load data
        try:
            inst_geo_df = pd.read_csv(institution_csv)
        except FileNotFoundError:
            print(f"  ⚠️  {institution_csv} not found. Skipping institution map.")
            return {"institution_pin_map_html": ""}
        
        if inst_geo_df.empty:
            print("  ⚠️  No institution geo data available.")
            return {"institution_pin_map_html": ""}
        
        # Limit to top N if specified
        if top_n is not None:
            inst_geo_df = inst_geo_df.head(top_n)
        
        # Build title with DOI
        doi_str = f" ({doi})" if doi else ""
        pin_title = f"Global Institutional Citation Footprint {doi_str}"
        
        # Create scatter map (requires plotly 5.0+)
        pin_fig = px.scatter_map(
            inst_geo_df,
            lat="latitude",
            lon="longitude",
            hover_name="institution_name",
            hover_data={
                "city": True,
                "country_code": True,
                "num_citing_papers": True,
                "latitude": False,
                "longitude": False
            },
            title=pin_title,
            zoom=1
        )
        
        pin_fig.update_traces(marker=dict(symbol="marker", size=10, opacity=0.8))
        lat_min, lat_max = inst_geo_df["latitude"].min(), inst_geo_df["latitude"].max()
        lon_min, lon_max = inst_geo_df["longitude"].min(), inst_geo_df["longitude"].max()

        pin_fig.update_layout(
            title=dict(
                    text=pin_title,
                    x=0.5,
                    xanchor="center",
                    y=0.98,
                    yanchor="top",
                    font=dict(
                        size=22,
                        family="Arial, sans-serif"
                    )
                ),
            mapbox_style="open-street-map",
            mapbox=dict(
                center=dict(lat=float((lat_min + lat_max)/2), lon=float((lon_min + lon_max)/2)),
                zoom=2
            ),
            margin=dict(l=10, r=10, t=90, b=10),
            height=700,
            width=1200
        )
        
        # Save HTML file
        pin_path = output_dir / f"{doi.replace('/', '_')}_citation_institution_pin_map.html"
        pin_fig.write_html(str(pin_path))
        
        # Try to save PNG file (optional, requires kaleido)
        try:
            pin_fig.write_image(str(output_dir / f"{doi.replace('/', '_')}_citation_institution_pin_map.png"), scale=2)
            print(f"  - {doi.replace('/', '_')}_citation_institution_pin_map.png")
        except Exception as e:
            print(f"  PNG export skipped (optional). Install kaleido for PNG support: pip install -U kaleido")
        
        print(f"\n✓ Saved institution pin map:")
        print(f"  - {pin_path.name}")
        
        return {"institution_pin_map_html": str(pin_path)}


def generate_citation_map(api_key: str, doi: str, output_dir: Optional[str] = None, top_n_institutions: Optional[int] = None) -> Dict:
    """
    One-shot function to generate complete citation analysis.
    
    Args:
        api_key: OpenAlex API key
        doi: Target paper DOI
        output_dir: Output directory (default: current directory)
        top_n_institutions: Limit institution map to top N institutions by citing count (optional)
        
    Returns:
        Dictionary with paths to all generated files:
          - citing_works: CSV path
          - country_counts: CSV path
          - edges: CSV path
          - nodes: CSV path
          - institution_geo: CSV path
          - map_html: Choropleth map HTML path
          - bar_html: Bar chart HTML path
          - institution_pin_map_html: Institution pin map HTML path
    
    Example:
        >>> results = generate_citation_map(
        ...     api_key="your_key",
        ...     doi="10.1016/j.apenergy.2022.119295",
        ...     output_dir="./output"
        ... )
        >>> print(results["map_html"])  # Path to interactive map
    """
    output_dir = Path(output_dir or ".")
    output_dir.mkdir(parents=True, exist_ok=True)
    
    generator = CitationMapGenerator(api_key)
    
    # Generate CSVs
    csv_files = generator.generate_csvs(doi, output_dir=output_dir)
    
    # Generate country-level HTML visualizations
    html_files = generator.generate_html_visualizations(
        csv_files["country_counts"],
        doi=doi,
        output_dir=output_dir
    )
    
    # Generate institution-level pin map
    inst_files = generator.generate_institution_pin_map(
        csv_files["institution_geo"],
        doi=doi,
        output_dir=output_dir,
        top_n=top_n_institutions
    )
    
    # Return all file paths
    all_files = {**csv_files, **html_files, **inst_files}
    
    print(f"\n✅ Complete! Output files:")
    for key, path in all_files.items():
        if path:  # Skip empty paths
            print(f"  {key}: {path}")
    
    return all_files


def generate_merged_citation_map(doi_list: List[str], output_dir: Optional[str] = None, top_n_institutions: Optional[int] = None) -> Dict:
    """
    Merge citation data from multiple DOIs and generate combined visualizations.
    
    Reads CSV files generated for each DOI, merges them, and creates unified visualizations.
    
    Args:
        doi_list: List of DOIs to merge (e.g., ["10.1016/j.trd.2021.103159", "10.1016/j.apenergy.2022.119295"])
        output_dir: Output directory for merged files (default: current directory)
        top_n_institutions: Limit merged institution map to top N institutions (optional)
        
    Returns:
        Dictionary with paths to merged files:
          - merged_country_counts: CSV path
          - merged_citing_works: CSV path
          - merged_edges: CSV path
          - merged_nodes: CSV path
          - merged_institution_geo: CSV path
          - merged_map_html: Choropleth map HTML path
          - merged_bar_html: Bar chart HTML path
          - merged_institution_pin_map_html: Institution pin map HTML path
    
    Example:
        >>> results = generate_merged_citation_map(
        ...     doi_list=["10.1016/j.trd.2021.103159", "10.1016/j.apenergy.2022.119295"],
        ...     output_dir="./doi_output"
        ... )
        >>> print(results["merged_map_html"])  # Path to merged interactive map
    """
    output_dir = Path(output_dir or ".")
    output_dir.mkdir(parents=True, exist_ok=True)
    
    generator = CitationMapGenerator("")  # Empty API key, not needed for merging
    
    print(f"\n🔗 Merging citation data from {len(doi_list)} DOIs:")
    for doi in doi_list:
        print(f"   - {doi}")
    
    all_country_dfs = []
    all_inst_geo_dfs = []
    all_citing_works_dfs = []
    all_edges_dfs = []
    all_nodes_dfs = []
    
    # Load CSVs for each DOI
    for doi in doi_list:
        doi_safe = doi.replace('/', '_')
        print(f"  Loading files for DOI: {doi}")
        
        # Try to load country counts
        country_csv = output_dir / f"{doi_safe}_country_counts.csv"
        if country_csv.exists():
            country_df = pd.read_csv(country_csv)
            country_df['source_doi'] = doi
            all_country_dfs.append(country_df)
        
        # Try to load institution geo data
        inst_csv = output_dir / f"{doi_safe}_institution_geo_counts.csv"
        if inst_csv.exists():
            inst_df = pd.read_csv(inst_csv)
            inst_df['source_doi'] = doi
            all_inst_geo_dfs.append(inst_df)
        
        # Try to load citing works
        citing_csv = output_dir / f"{doi_safe}_citing_works.csv"
        if citing_csv.exists():
            citing_df = pd.read_csv(citing_csv)
            citing_df['source_doi'] = doi
            all_citing_works_dfs.append(citing_df)
        
        # Try to load edges
        edges_csv = output_dir / f"{doi_safe}_edges.csv"
        if edges_csv.exists():
            edges_df = pd.read_csv(edges_csv)
            edges_df['source_doi'] = doi
            all_edges_dfs.append(edges_df)
        
        # Try to load nodes
        nodes_csv = output_dir / f"{doi_safe}_nodes.csv"
        if nodes_csv.exists():
            nodes_df = pd.read_csv(nodes_csv)
            nodes_df['source_doi'] = doi
            all_nodes_dfs.append(nodes_df)
    
    if not all_country_dfs:
        raise RuntimeError(f"No CSV files found for the provided DOIs in {output_dir}")
    
    # Merge country counts
    print("  Merging country counts...")
    merged_country_df = pd.concat(all_country_dfs, ignore_index=True)
    merged_country_df = merged_country_df.groupby('country_code', as_index=False)['num_citing_papers'].sum()
    merged_country_df = merged_country_df.sort_values('num_citing_papers', ascending=False).reset_index(drop=True)
    
    # Merge institution geo data
    print("  Merging institution geo data...")
    if all_inst_geo_dfs:
        merged_inst_geo_df = pd.concat(all_inst_geo_dfs, ignore_index=True)
        # Group by institution ID and sum citing papers, keeping other fields from first occurrence
        merged_inst_geo_df = merged_inst_geo_df.groupby('institution_id', as_index=False).agg({
            'institution_name': 'first',
            'country_code': 'first',
            'city': 'first',
            'latitude': 'first',
            'longitude': 'first',
            'num_citing_papers': 'sum'
        })
        merged_inst_geo_df = merged_inst_geo_df.sort_values('num_citing_papers', ascending=False).reset_index(drop=True)
    else:
        merged_inst_geo_df = pd.DataFrame()
    
    # Merge citing works
    print("  Merging citing works...")
    if all_citing_works_dfs:
        merged_citing_df = pd.concat(all_citing_works_dfs, ignore_index=True)
        merged_citing_df = merged_citing_df.drop_duplicates(subset=['citing_openalex_id']).reset_index(drop=True)
    else:
        merged_citing_df = pd.DataFrame()
    
    # Merge edges
    print("  Merging edges...")
    if all_edges_dfs:
        merged_edges_df = pd.concat(all_edges_dfs, ignore_index=True)
        merged_edges_df = merged_edges_df.drop_duplicates().reset_index(drop=True)
    else:
        merged_edges_df = pd.DataFrame()
    
    # Merge nodes
    print("  Merging nodes...")
    if all_nodes_dfs:
        merged_nodes_df = pd.concat(all_nodes_dfs, ignore_index=True)
        merged_nodes_df = merged_nodes_df.drop_duplicates(subset=['id']).reset_index(drop=True)
    else:
        merged_nodes_df = pd.DataFrame()
    
    # Save merged CSVs with simple naming
    files = {
        "merged_country_counts": output_dir / "merged_country_counts.csv",
        "merged_institution_geo": output_dir / "merged_institution_geo_counts.csv",
        "merged_citing_works": output_dir / "merged_citing_works.csv",
        "merged_edges": output_dir / "merged_edges.csv",
        "merged_nodes": output_dir / "merged_nodes.csv",
    }
    
    merged_country_df.to_csv(files["merged_country_counts"], index=False)
    merged_inst_geo_df.to_csv(files["merged_institution_geo"], index=False)
    merged_citing_df.to_csv(files["merged_citing_works"], index=False)
    merged_edges_df.to_csv(files["merged_edges"], index=False)
    merged_nodes_df.to_csv(files["merged_nodes"], index=False)
    
    # Print merge summary
    print(f"\n📊 Merge Summary:")
    print(f"  Unique Countries: {len(merged_country_df)}")
    print(f"  Total Citing Papers (Countries): {merged_country_df['num_citing_papers'].sum()}")
    if not merged_inst_geo_df.empty:
        print(f"  Unique Institutions: {len(merged_inst_geo_df)}")
        print(f"  Total Citing Papers (Institutions): {merged_inst_geo_df['num_citing_papers'].sum()}")
    if not merged_citing_df.empty:
        print(f"  Unique Citing Works: {len(merged_citing_df)}")
    
    print(f"\n✓ Saved merged CSV files to {output_dir}:")
    for key, path in files.items():
        print(f"  - {path.name}")
    
    # Generate merged visualizations
    print("\n🗺️  Generating merged HTML visualizations...")
    html_files = generator.generate_html_visualizations(
        str(files["merged_country_counts"]),
        doi="Top Cited Papers",
        output_dir=output_dir
    )
    
    print("\n📍 Generating merged institution pin map...")
    inst_files = generator.generate_institution_pin_map(
        str(files["merged_institution_geo"]),
        doi="Top Cited Papers",
        output_dir=output_dir,
        top_n=top_n_institutions
    )
    
    # Combine all results
    all_files = {k: str(v) for k, v in files.items()}
    all_files.update(html_files)
    all_files.update(inst_files)
    
    print(f"\n✅ Complete! Merged output files:")
    for key, path in all_files.items():
        if path:
            print(f"  {key}: {path}")
    
    return all_files


if __name__ == "__main__":
    # Example usage
    import sys
    
    if len(sys.argv) < 3:
        print("Usage: python citation_map_generator.py <API_KEY> <DOI> [OUTPUT_DIR] [TOP_N_INSTITUTIONS]")
        print("")
        print("Error: DOI is required as the second argument.")
        sys.exit(1)

    api_key = sys.argv[1]
    doi = sys.argv[2]
    output_dir = sys.argv[3] if len(sys.argv) > 3 else None
    top_n_institutions = int(sys.argv[4]) if len(sys.argv) > 4 else None
    
    try:
        results = generate_citation_map(
            api_key,
            doi,
            output_dir,
            top_n_institutions=top_n_institutions
        )
    except Exception as e:
        print(f"\n❌ Error: {e}")
        sys.exit(1)
