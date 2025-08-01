#!/usr/bin/env python3
"""
Literature Review Alert System - GitHub Pages Version
Searches PubMed for recent papers and generates a website + RSS feed
"""

import os
import sys
import requests
import json
from datetime import datetime, timedelta
from urllib.parse import quote
import time
from pathlib import Path

def search_pubmed(keywords, days_back=1):
    """Search PubMed for recent papers matching keywords"""
    base_url = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/"

    # Calculate date range
    end_date = datetime.now()
    start_date = end_date - timedelta(days=int(days_back))

    date_filter = f"{start_date.strftime('%Y/%m/%d')}:{end_date.strftime('%Y/%m/%d')}[pdat]"

    results = []

    for keyword_set in keywords:
        print(f"Searching for: {keyword_set}")

        # Build search query
        query = f"({keyword_set}) AND {date_filter}"

        # Search for paper IDs
        search_url = f"{base_url}esearch.fcgi"
        search_params = {
            'db': 'pubmed',
            'term': query,
            'retmax': 20,  # Limit to most recent 20 papers per keyword set
            'sort': 'pub_date',
            'retmode': 'json'
        }

        try:
            search_response = requests.get(search_url, params=search_params, timeout=30)
            search_data = search_response.json()

            if 'esearchresult' in search_data and 'idlist' in search_data['esearchresult']:
                paper_ids = search_data['esearchresult']['idlist']

                if paper_ids:
                    # Get paper details
                    papers = fetch_paper_details(paper_ids)
                    for paper in papers:
                        paper['search_term'] = keyword_set
                    results.extend(papers)

        except Exception as e:
            print(f"Error searching for {keyword_set}: {e}")

        # Be nice to NCBI servers
        time.sleep(0.5)

    return results

def fetch_paper_details(paper_ids):
    """Fetch detailed information for papers"""
    base_url = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/"

    # Get detailed info
    fetch_url = f"{base_url}efetch.fcgi"
    fetch_params = {
        'db': 'pubmed',
        'id': ','.join(paper_ids),
        'retmode': 'xml'
    }

    papers = []

    try:
        response = requests.get(fetch_url, params=fetch_params, timeout=30)

        # Simple XML parsing for key fields
        xml_content = response.text

        # Split by articles (basic approach)
        articles = xml_content.split('<PubmedArticle>')

        for article in articles[1:]:  # Skip first empty split
            paper = extract_paper_info(article)
            if paper:
                papers.append(paper)

    except Exception as e:
        print(f"Error fetching paper details: {e}")

    return papers

def extract_paper_info(article_xml):
    """Extract key information from article XML"""
    try:
        # Basic regex-like extraction (simple but effective)
        import re

        # Extract title
        title_match = re.search(r'<ArticleTitle>(.*?)</ArticleTitle>', article_xml, re.DOTALL)
        title = title_match.group(1).strip() if title_match else "Title not found"

        # Extract authors (first few)
        author_pattern = r'<LastName>(.*?)</LastName>.*?<ForeName>(.*?)</ForeName>'
        authors = re.findall(author_pattern, article_xml)
        author_str = ", ".join([f"{first} {last}" for last, first in authors[:3]])
        if len(authors) > 3:
            author_str += " et al."

        # Extract journal
        journal_match = re.search(r'<Title>(.*?)</Title>', article_xml)
        journal = journal_match.group(1) if journal_match else "Journal not found"

        # Extract PMID
        pmid_match = re.search(r'<PMID.*?>(.*?)</PMID>', article_xml)
        pmid = pmid_match.group(1) if pmid_match else None

        # Extract publication date
        pub_date_match = re.search(r'<PubDate>.*?<Year>(\d{4})</Year>.*?<Month>(\w+)</Month>.*?<Day>(\d+)</Day>', article_xml, re.DOTALL)
        if pub_date_match:
            year, month_name, day = pub_date_match.groups()
            # Convert month name to number
            month_map = {'Jan': 1, 'Feb': 2, 'Mar': 3, 'Apr': 4, 'May': 5, 'Jun': 6,
                        'Jul': 7, 'Aug': 8, 'Sep': 9, 'Oct': 10, 'Nov': 11, 'Dec': 12}
            month = month_map.get(month_name[:3], 1)
            pub_date = f"{year}-{month:02d}-{int(day):02d}"
        else:
            pub_date = datetime.now().strftime('%Y-%m-%d')

        # Extract abstract
        abstract_match = re.search(r'<AbstractText.*?>(.*?)</AbstractText>', article_xml, re.DOTALL)
        abstract = abstract_match.group(1).strip() if abstract_match else "Abstract not available"

        # Clean up HTML entities
        title = title.replace('&lt;', '<').replace('&gt;', '>').replace('&amp;', '&')
        abstract = abstract.replace('&lt;', '<').replace('&gt;', '>').replace('&amp;', '&')

        return {
            'title': title,
            'authors': author_str,
            'journal': journal,
            'pmid': pmid,
            'pub_date': pub_date,
            'abstract': abstract,
            'url': f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/" if pmid else None
        }

    except Exception as e:
        print(f"Error extracting paper info: {e}")
        return None

def calculate_relevance_score(paper, keywords):
    """Simple relevance scoring based on keyword matches"""
    text_to_check = (paper['title'] + ' ' + paper['abstract']).lower()

    score = 0
    matched_terms = []

    for keyword_set in keywords:
        keyword_terms = keyword_set.lower().replace('(', '').replace(')', '').replace(' and ', ' ').replace(' or ', ' ').split()
        for term in keyword_terms:
            if len(term) > 2 and term in text_to_check:  # Skip very short terms
                score += text_to_check.count(term)
                if term not in matched_terms:
                    matched_terms.append(term)

    paper['relevance_score'] = score
    paper['matched_terms'] = matched_terms
    return paper

def load_historical_data():
    """Load historical papers from JSON file"""
    try:
        with open('docs/papers.json', 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        return []

def save_papers_data(papers):
    """Save all papers to JSON file"""
    os.makedirs('docs', exist_ok=True)
    with open('docs/papers.json', 'w') as f:
        json.dump(papers, f, indent=2, default=str)

def generate_main_html(papers):
    """Generate main HTML page"""

    # Group papers by date
    papers_by_date = {}
    for paper in papers:
        date = paper['pub_date']
        if date not in papers_by_date:
            papers_by_date[date] = []
        papers_by_date[date].append(paper)

    # Sort dates (newest first)
    sorted_dates = sorted(papers_by_date.keys(), reverse=True)

    repo_name = os.getenv('REPO_NAME', 'your-repo').split('/')[-1]

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Literature Review - {repo_name}</title>
    <link rel="alternate" type="application/rss+xml" title="Literature Feed" href="feed.xml">
    <style>
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            max-width: 1000px;
            margin: 0 auto;
            padding: 20px;
            background: #fafafa;
        }}
        .header {{
            text-align: center;
            margin-bottom: 40px;
            padding: 30px;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            border-radius: 10px;
        }}
        .stats {{
            display: flex;
            justify-content: center;
            gap: 30px;
            margin: 20px 0;
            flex-wrap: wrap;
        }}
        .stat {{
            background: rgba(255,255,255,0.2);
            padding: 10px 20px;
            border-radius: 20px;
            font-weight: bold;
        }}
        .date-section {{
            margin: 30px 0;
            background: white;
            border-radius: 10px;
            overflow: hidden;
            box-shadow: 0 4px 6px rgba(0,0,0,0.1);
        }}
        .date-header {{
            background: #4CAF50;
            color: white;
            padding: 15px 20px;
            font-weight: bold;
            font-size: 18px;
        }}
        .paper {{
            border-bottom: 1px solid #eee;
            padding: 20px;
            position: relative;
        }}
        .paper:last-child {{ border-bottom: none; }}
        .high-relevance {{
            border-left: 4px solid #FF5722;
            background: linear-gradient(90deg, #fff5f5 0%, white 20%);
        }}
        .medium-relevance {{
            border-left: 4px solid #FF9800;
            background: linear-gradient(90deg, #fffbf0 0%, white 20%);
        }}
        .low-relevance {{
            border-left: 4px solid #4CAF50;
        }}
        .title {{
            font-size: 18px;
            font-weight: bold;
            color: #333;
            margin-bottom: 8px;
            line-height: 1.3;
        }}
        .title a {{
            color: #333;
            text-decoration: none;
        }}
        .title a:hover {{
            color: #1976D2;
            text-decoration: underline;
        }}
        .authors {{
            color: #666;
            font-style: italic;
            margin: 5px 0;
        }}
        .journal {{
            color: #2196F3;
            font-weight: bold;
            margin: 5px 0;
        }}
        .abstract {{
            margin: 15px 0;
            line-height: 1.5;
            color: #444;
        }}
        .metadata {{
            font-size: 13px;
            color: #888;
            display: flex;
            flex-wrap: wrap;
            gap: 15px;
            align-items: center;
        }}
        .matched-terms {{
            background: #FFE082;
            padding: 2px 6px;
            border-radius: 12px;
            font-size: 11px;
            font-weight: bold;
        }}
        .relevance-badge {{
            position: absolute;
            top: 15px;
            right: 15px;
            padding: 4px 8px;
            border-radius: 12px;
            font-size: 11px;
            font-weight: bold;
            color: white;
        }}
        .high-score {{ background: #F44336; }}
        .medium-score {{ background: #FF9800; }}
        .low-score {{ background: #4CAF50; }}
        .rss-link {{
            position: fixed;
            top: 20px;
            right: 20px;
            background: #FF6600;
            color: white;
            padding: 10px 15px;
            border-radius: 20px;
            text-decoration: none;
            font-weight: bold;
            box-shadow: 0 2px 10px rgba(0,0,0,0.2);
            z-index: 1000;
        }}
        .rss-link:hover {{
            background: #E55A00;
            transform: translateY(-2px);
            transition: all 0.2s;
        }}
        .search-box {{
            width: 100%;
            max-width: 400px;
            padding: 10px 15px;
            border: 2px solid rgba(255,255,255,0.3);
            border-radius: 25px;
            background: rgba(255,255,255,0.2);
            color: white;
            font-size: 16px;
            margin: 10px 0;
        }}
        .search-box::placeholder {{
            color: rgba(255,255,255,0.8);
        }}
        @media (max-width: 600px) {{
            .stats {{ flex-direction: column; align-items: center; }}
            .metadata {{ flex-direction: column; align-items: flex-start; }}
            .relevance-badge {{ position: static; margin-bottom: 10px; }}
        }}
    </style>
</head>
<body>
    <a href="feed.xml" class="rss-link">📡 RSS Feed</a>

    <div class="header">
        <h1>🧠 Literature Review Dashboard</h1>
        <p>Automated neuroscience literature tracking</p>
        <input type="text" class="search-box" id="searchBox" placeholder="Search papers...">

        <div class="stats">
            <div class="stat">📚 {len(papers)} Total Papers</div>
            <div class="stat">📅 {len(sorted_dates)} Days Tracked</div>
            <div class="stat">🔥 {len([p for p in papers if p.get('relevance_score', 0) >= 5])} High Relevance</div>
            <div class="stat">⚡ Last Updated: {datetime.now().strftime('%Y-%m-%d %H:%M UTC')}</div>
        </div>
    </div>

    <div id="papersContainer">
"""

    # Add papers grouped by date
    for date in sorted_dates[:30]:  # Show last 30 days
        papers_on_date = papers_by_date[date]
        papers_sorted = sorted(papers_on_date, key=lambda x: x.get('relevance_score', 0), reverse=True)

        html += f"""
        <div class="date-section">
            <div class="date-header">
                📅 {date} ({len(papers_on_date)} papers)
            </div>
        """

        for paper in papers_sorted:
            relevance = paper.get('relevance_score', 0)

            if relevance >= 5:
                relevance_class = "high-relevance"
                badge_class = "high-score"
                badge_text = "🔥 HIGH"
            elif relevance >= 2:
                relevance_class = "medium-relevance"
                badge_class = "medium-score"
                badge_text = "⚡ MED"
            else:
                relevance_class = "low-relevance"
                badge_class = "low-score"
                badge_text = "✓ LOW"

            # Truncate abstract for display
            abstract_display = paper['abstract'][:300] + "..." if len(paper['abstract']) > 300 else paper['abstract']

            paper_title = paper['title'] if paper.get('url') else paper['title']
            title_html = f'<a href="{paper["url"]}" target="_blank">{paper_title}</a>' if paper.get('url') else paper_title

            html += f"""
            <div class="paper {relevance_class}" data-title="{paper['title'].lower()}" data-abstract="{paper['abstract'].lower()}">
                <div class="relevance-badge {badge_class}">{badge_text}</div>
                <div class="title">{title_html}</div>
                <div class="authors">{paper['authors']}</div>
                <div class="journal">{paper['journal']}</div>
                <div class="abstract">{abstract_display}</div>
                <div class="metadata">
                    <span>Relevance: {relevance}</span>
                    <span class="matched-terms">{', '.join(paper.get('matched_terms', []))}</span>
                    <span>PMID: {paper.get('pmid', 'N/A')}</span>
                </div>
            </div>
            """

        html += "</div>"

    html += """
    </div>

    <footer style="text-align: center; margin-top: 50px; padding: 20px; color: #666;">
        <p><em>🤖 Generated automatically by GitHub Actions Literature Review System</em></p>
        <p>Configure keywords in repository variables to customize your alerts</p>
    </footer>

    <script>
        // Simple search functionality
        document.getElementById('searchBox').addEventListener('input', function(e) {
            const searchTerm = e.target.value.toLowerCase();
            const papers = document.querySelectorAll('.paper');

            papers.forEach(paper => {
                const title = paper.dataset.title || '';
                const abstract = paper.dataset.abstract || '';

                if (title.includes(searchTerm) || abstract.includes(searchTerm)) {
                    paper.style.display = 'block';
                } else {
                    paper.style.display = 'none';
                }
            });

            // Hide empty date sections
            document.querySelectorAll('.date-section').forEach(section => {
                const visiblePapers = section.querySelectorAll('.paper[style="display: block"], .paper:not([style*="display: none"])');
                section.style.display = visiblePapers.length > 0 ? 'block' : 'none';
            });
        });
    </script>
</body>
</html>
"""

    return html

def generate_rss_feed(papers):
    """Generate RSS feed XML"""
    repo_name = os.getenv('REPO_NAME', 'literature-review').split('/')[-1]
    base_url = f"https://{os.getenv('REPO_NAME', 'user/repo').replace('/', '.github.io/')}"

    # Sort papers by date (newest first)
    papers_sorted = sorted(papers, key=lambda x: x['pub_date'], reverse=True)[:50]  # Last 50 papers

    rss = f"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0" xmlns:atom="http://www.w3.org/2005/Atom">
<channel>
    <title>Literature Review - {repo_name}</title>
    <description>Automated neuroscience literature tracking</description>
    <link>{base_url}</link>
    <atom:link href="{base_url}/feed.xml" rel="self" type="application/rss+xml"/>
    <lastBuildDate>{datetime.now().strftime('%a, %d %b %Y %H:%M:%S %z')}</lastBuildDate>
    <language>en-us</language>
    <generator>GitHub Actions Literature Review System</generator>
"""

    for paper in papers_sorted:
        # Create item description
        description = f"""
        <![CDATA[
        <p><strong>Authors:</strong> {paper['authors']}</p>
        <p><strong>Journal:</strong> {paper['journal']}</p>
        <p><strong>Relevance Score:</strong> {paper.get('relevance_score', 0)}</p>
        <p><strong>Matched Terms:</strong> {', '.join(paper.get('matched_terms', []))}</p>
        <br>
        <p>{paper['abstract']}</p>
        ]]>
        """

        # Convert date to RFC 2822 format
        try:
            pub_date = datetime.strptime(paper['pub_date'], '%Y-%m-%d')
            pub_date_rfc = pub_date.strftime('%a, %d %b %Y 00:00:00 +0000')
        except:
            pub_date_rfc = datetime.now().strftime('%a, %d %b %Y %H:%M:%S +0000')

        rss += f"""
    <item>
        <title>{paper['title']}</title>
        <link>{paper.get('url', base_url)}</link>
        <description>{description}</description>
        <pubDate>{pub_date_rfc}</pubDate>
        <guid>{paper.get('url', f"{base_url}#{paper.get('pmid', 'unknown')}")}</guid>
    </item>
"""

    rss += """
</channel>
</rss>
"""

    return rss

def main():
    """Main function"""
    # Get configuration from environment
    keywords_raw = os.getenv('RESEARCH_KEYWORDS', 'fMRI,EEG,neural networks')
    days_back = os.getenv('DAYS_BACK', '1')

    # Parse keywords (semicolon-separated sets)
    keywords = [kw.strip() for kw in keywords_raw.split(';')]

    print(f"Searching for papers from last {days_back} days...")
    print(f"Keywords: {keywords}")

    # Load historical data
    historical_papers = load_historical_data()
    print(f"Loaded {len(historical_papers)} historical papers")

    # Search for new papers
    new_papers = search_pubmed(keywords, days_back)

    if new_papers:
        # Calculate relevance scores for new papers
        new_papers_with_scores = [calculate_relevance_score(paper, keywords) for paper in new_papers]

        # Combine with historical data, removing duplicates
        all_papers = {}

        # Add historical papers
        for paper in historical_papers:
            pmid = paper.get('pmid')
            if pmid:
                all_papers[pmid] = paper

        # Add new papers (will override if duplicate)
        for paper in new_papers_with_scores:
            pmid = paper.get('pmid')
            if pmid:
                all_papers[pmid] = paper

        final_papers = list(all_papers.values())

        print(f"Found {len(new_papers_with_scores)} new papers")
        print(f"Total papers in database: {len(final_papers)}")

        # Save updated papers data
        save_papers_data(final_papers)

        # Generate HTML page
        html_content = generate_main_html(final_papers)
        with open('docs/index.html', 'w', encoding='utf-8') as f:
            f.write(html_content)

        # Generate RSS feed
        rss_content = generate_rss_feed(final_papers)
        with open('docs/feed.xml', 'w', encoding='utf-8') as f:
            f.write(rss_content)

        print("Generated HTML page and RSS feed in docs/ directory")

    else:
        print("No new papers found, but updating website with existing data")

        # Still generate pages with historical data
        if historical_papers:
            html_content = generate_main_html(historical_papers)
            with open('docs/index.html', 'w', encoding='utf-8') as f:
                f.write(html_content)

            rss_content = generate_rss_feed(historical_papers)
            with open('docs/feed.xml', 'w', encoding='utf-8') as f:
                f.write(rss_content)

if __name__ == "__main__":
    main()