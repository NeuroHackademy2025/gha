#!/usr/bin/env python3
"""
Grant Deadline Tracker
Scrapes funding opportunities and tracks deadlines automatically
"""

import os
import sys
import requests
import json
from datetime import datetime, timedelta
from pathlib import Path
import time
import re
from urllib.parse import urljoin, urlparse
from bs4 import BeautifulSoup

class GrantTracker:
    def __init__(self):
        self.grants = []
        self.research_areas = self.parse_research_areas()
        self.institution_type = os.getenv('INSTITUTION_TYPE', 'university').lower()
        self.career_stage = os.getenv('CAREER_STAGE', 'postdoc').lower()

    def parse_research_areas(self):
        """Parse research areas from environment"""
        areas_raw = os.getenv('RESEARCH_AREAS', 'neuroscience,cognitive science,brain imaging')
        return [area.strip().lower() for area in areas_raw.split(',')]

    def scrape_nih_grants(self):
        """Scrape NIH funding opportunities"""
        print("Scraping NIH grants...")

        try:
            # NIH Guide for Grants and Contracts
            url = "https://grants.nih.gov/funding/searchguide/index.html"
            response = requests.get(url, timeout=30)
            soup = BeautifulSoup(response.content, 'html.parser')

            # Look for funding announcements
            grant_links = soup.find_all('a', href=re.compile(r'guide.*\.html'))

            for link in grant_links[:20]:  # Limit to avoid overwhelming
                try:
                    grant_url = urljoin(url, link.get('href'))
                    grant_data = self.parse_nih_grant_page(grant_url)
                    if grant_data and self.is_relevant_grant(grant_data):
                        self.grants.append(grant_data)
                    time.sleep(1)  # Be respectful
                except Exception as e:
                    print(f"Error parsing NIH grant {link.get('href')}: {e}")

        except Exception as e:
            print(f"Error scraping NIH: {e}")

    def parse_nih_grant_page(self, url):
        """Parse individual NIH grant page"""
        try:
            response = requests.get(url, timeout=20)
            soup = BeautifulSoup(response.content, 'html.parser')

            # Extract title
            title_elem = soup.find('h1') or soup.find('title')
            title = title_elem.get_text().strip() if title_elem else "Unknown Title"

            # Extract deadlines - look for common date patterns
            text_content = soup.get_text()
            deadline_patterns = [
                r'application.*due.*?(\w+\s+\d{1,2},?\s+\d{4})',
                r'deadline.*?(\w+\s+\d{1,2},?\s+\d{4})',
                r'submit.*by.*?(\w+\s+\d{1,2},?\s+\d{4})',
                r'due\s+date.*?(\w+\s+\d{1,2},?\s+\d{4})'
            ]

            deadlines = []
            for pattern in deadline_patterns:
                matches = re.findall(pattern, text_content, re.IGNORECASE)
                for match in matches:
                    try:
                        deadline_date = datetime.strptime(match.strip(), '%B %d, %Y')
                        if deadline_date > datetime.now():
                            deadlines.append(deadline_date)
                    except:
                        try:
                            deadline_date = datetime.strptime(match.strip(), '%B %d %Y')
                            if deadline_date > datetime.now():
                                deadlines.append(deadline_date)
                        except:
                            pass

            # Extract award amount
            amount_patterns = [
                r'\$([0-9,]+(?:\.[0-9]{2})?)',
                r'award.*?([0-9,]+)',
                r'budget.*?([0-9,]+)'
            ]

            amounts = []
            for pattern in amount_patterns:
                matches = re.findall(pattern, text_content, re.IGNORECASE)
                for match in matches:
                    try:
                        amount = int(match.replace(',', '').replace('$', ''))
                        if 1000 <= amount <= 10000000:  # Reasonable grant range
                            amounts.append(amount)
                    except:
                        pass

            # Extract program info
            program_elem = soup.find('meta', {'name': 'description'})
            description = program_elem.get('content', '')[:500] if program_elem else ''

            if not description:
                # Try to find description in content
                desc_candidates = soup.find_all('p')
                for p in desc_candidates[:5]:
                    if len(p.get_text().strip()) > 100:
                        description = p.get_text().strip()[:500]
                        break

            return {
                'title': title,
                'agency': 'NIH',
                'url': url,
                'deadlines': deadlines,
                'amounts': amounts,
                'description': description,
                'last_updated': datetime.now(),
                'source_type': 'nih'
            }

        except Exception as e:
            print(f"Error parsing NIH grant page {url}: {e}")
            return None

    def scrape_nsf_grants(self):
        """Scrape NSF funding opportunities"""
        print("Scraping NSF grants...")

        try:
            # NSF funding search
            base_url = "https://www.nsf.gov"
            search_url = f"{base_url}/funding/"

            response = requests.get(search_url, timeout=30)
            soup = BeautifulSoup(response.content, 'html.parser')

            # Look for funding opportunity links
            funding_links = soup.find_all('a', href=re.compile(r'funding|solicitation'))

            for link in funding_links[:15]:  # Limit requests
                try:
                    grant_url = urljoin(base_url, link.get('href'))
                    if self.is_nsf_grant_page(grant_url):
                        grant_data = self.parse_nsf_grant_page(grant_url)
                        if grant_data and self.is_relevant_grant(grant_data):
                            self.grants.append(grant_data)
                    time.sleep(1)
                except Exception as e:
                    print(f"Error parsing NSF grant {link.get('href')}: {e}")

        except Exception as e:
            print(f"Error scraping NSF: {e}")

    def is_nsf_grant_page(self, url):
        """Check if URL is likely an NSF grant page"""
        nsf_indicators = ['solicitation', 'funding', 'pubs', 'nsf.gov']
        return any(indicator in url.lower() for indicator in nsf_indicators)

    def parse_nsf_grant_page(self, url):
        """Parse individual NSF grant page"""
        try:
            response = requests.get(url, timeout=20)
            soup = BeautifulSoup(response.content, 'html.parser')

            # Extract title
            title_elem = soup.find('h1') or soup.find('title')
            title = title_elem.get_text().strip() if title_elem else "Unknown NSF Grant"

            # Extract deadlines
            text_content = soup.get_text()
            deadline_patterns = [
                r'proposal.*due.*?(\w+\s+\d{1,2},?\s+\d{4})',
                r'deadline.*?(\w+\s+\d{1,2},?\s+\d{4})',
                r'submit.*by.*?(\w+\s+\d{1,2},?\s+\d{4})',
                r'full proposal.*?(\w+\s+\d{1,2},?\s+\d{4})'
            ]

            deadlines = []
            for pattern in deadline_patterns:
                matches = re.findall(pattern, text_content, re.IGNORECASE)
                for match in matches:
                    try:
                        deadline_date = datetime.strptime(match.strip(), '%B %d, %Y')
                        if deadline_date > datetime.now():
                            deadlines.append(deadline_date)
                    except:
                        pass

            # NSF grants often have standard amounts
            amount_patterns = [
                r'\$([0-9,]+(?:\.[0-9]{2})?)',
                r'award.*?([0-9,]+)',
                r'maximum.*?([0-9,]+)'
            ]

            amounts = []
            for pattern in amount_patterns:
                matches = re.findall(pattern, text_content, re.IGNORECASE)
                for match in matches:
                    try:
                        amount = int(match.replace(',', '').replace('$', ''))
                        if 5000 <= amount <= 5000000:  # NSF range
                            amounts.append(amount)
                    except:
                        pass

            description = soup.find('meta', {'name': 'description'})
            description = description.get('content', '')[:500] if description else text_content[:500]

            return {
                'title': title,
                'agency': 'NSF',
                'url': url,
                'deadlines': deadlines,
                'amounts': amounts,
                'description': description,
                'last_updated': datetime.now(),
                'source_type': 'nsf'
            }

        except Exception as e:
            print(f"Error parsing NSF grant page {url}: {e}")
            return None

    def scrape_foundation_grants(self):
        """Scrape major foundation grants"""
        print("Scraping foundation grants...")

        foundations = [
            {
                'name': 'Brain & Behavior Research Foundation',
                'url': 'https://www.bbrfoundation.org/grants-prizes',
                'keywords': ['brain', 'behavior', 'mental health', 'psychiatry']
            },
            {
                'name': 'Simons Foundation',
                'url': 'https://www.simonsfoundation.org/funding-opportunities/',
                'keywords': ['autism', 'neuroscience', 'mathematics']
            },
            {
                'name': 'Dana Foundation',
                'url': 'https://dana.org/grants/',
                'keywords': ['brain', 'neuroscience', 'neuroimmunology']
            }
        ]

        for foundation in foundations:
            try:
                print(f"Scraping {foundation['name']}...")
                grants = self.scrape_foundation_page(foundation)
                self.grants.extend(grants)
                time.sleep(2)  # Be respectful
            except Exception as e:
                print(f"Error scraping {foundation['name']}: {e}")

    def scrape_foundation_page(self, foundation):
        """Scrape individual foundation page"""
        try:
            response = requests.get(foundation['url'], timeout=30)
            soup = BeautifulSoup(response.content, 'html.parser')

            grants = []

            # Look for grant-related content
            grant_sections = soup.find_all(['div', 'section'], class_=re.compile(r'grant|funding|opportunity', re.I))

            for section in grant_sections[:5]:  # Limit to avoid noise
                title_elem = section.find(['h1', 'h2', 'h3', 'h4'])
                if not title_elem:
                    continue

                title = title_elem.get_text().strip()

                # Extract text content for deadline searching
                section_text = section.get_text()

                # Look for deadlines
                deadline_patterns = [
                    r'deadline.*?(\w+\s+\d{1,2},?\s+\d{4})',
                    r'due.*?(\w+\s+\d{1,2},?\s+\d{4})',
                    r'apply.*by.*?(\w+\s+\d{1,2},?\s+\d{4})',
                    r'submission.*?(\w+\s+\d{1,2},?\s+\d{4})'
                ]

                deadlines = []
                for pattern in deadline_patterns:
                    matches = re.findall(pattern, section_text, re.IGNORECASE)
                    for match in matches:
                        try:
                            deadline_date = datetime.strptime(match.strip(), '%B %d, %Y')
                            if deadline_date > datetime.now():
                                deadlines.append(deadline_date)
                        except:
                            pass

                # Extract amounts
                amounts = []
                amount_matches = re.findall(r'\$([0-9,]+)', section_text)
                for match in amount_matches:
                    try:
                        amount = int(match.replace(',', ''))
                        if 1000 <= amount <= 10000000:
                            amounts.append(amount)
                    except:
                        pass

                if title and (deadlines or 'grant' in title.lower()):
                    grants.append({
                        'title': title,
                        'agency': foundation['name'],
                        'url': foundation['url'],
                        'deadlines': deadlines,
                        'amounts': amounts,
                        'description': section_text[:300].strip(),
                        'last_updated': datetime.now(),
                        'source_type': 'foundation'
                    })

            return grants

        except Exception as e:
            print(f"Error scraping foundation page: {e}")
            return []

    def scrape_static_opportunities(self):
        """Add known static grant opportunities with regular deadlines"""
        print("Adding known grant opportunities...")

        static_grants = [
            {
                'title': 'NIH F31 Predoctoral Fellowship',
                'agency': 'NIH',
                'url': 'https://grants.nih.gov/grants/guide/pa-files/PA-23-271.html',
                'deadlines': self.generate_recurring_deadlines(['April 8', 'August 8', 'December 8']),
                'amounts': [25000, 30000],
                'description': 'Predoctoral fellowships for graduate students conducting dissertation research.',
                'last_updated': datetime.now(),
                'source_type': 'static',
                'eligibility': ['graduate student', 'phd']
            },
            {
                'title': 'NIH F32 Postdoctoral Fellowship',
                'agency': 'NIH',
                'url': 'https://grants.nih.gov/grants/guide/pa-files/PA-23-272.html',
                'deadlines': self.generate_recurring_deadlines(['April 8', 'August 8', 'December 8']),
                'amounts': [50000, 60000],
                'description': 'Postdoctoral fellowships for recent PhD recipients.',
                'last_updated': datetime.now(),
                'source_type': 'static',
                'eligibility': ['postdoc', 'recent phd']
            },
            {
                'title': 'NIH K01 Career Development Award',
                'agency': 'NIH',
                'url': 'https://grants.nih.gov/grants/guide/pa-files/PA-23-273.html',
                'deadlines': self.generate_recurring_deadlines(['February 12', 'June 12', 'October 12']),
                'amounts': [100000, 150000],
                'description': 'Career development awards for early-career investigators.',
                'last_updated': datetime.now(),
                'source_type': 'static',
                'eligibility': ['assistant professor', 'early career']
            },
            {
                'title': 'NSF Graduate Research Fellowship',
                'agency': 'NSF',
                'url': 'https://www.nsfgrfp.org/',
                'deadlines': [datetime(2025, 10, 15)],  # Typically October
                'amounts': [37000, 46000],
                'description': 'Fellowship for outstanding graduate students in STEM fields.',
                'last_updated': datetime.now(),
                'source_type': 'static',
                'eligibility': ['graduate student', 'early graduate']
            },
            {
                'title': 'Brain & Behavior Research Foundation Young Investigator Grant',
                'agency': 'Brain & Behavior Research Foundation',
                'url': 'https://www.bbrfoundation.org/grants-prizes/young-investigator-grants',
                'deadlines': [datetime(2025, 9, 15)],  # Typically September
                'amounts': [70000],
                'description': 'Grants for early-career investigators in brain and behavior research.',
                'last_updated': datetime.now(),
                'source_type': 'static',
                'eligibility': ['postdoc', 'assistant professor']
            },
            {
                'title': 'Simons Foundation Autism Research Initiative (SFARI)',
                'agency': 'Simons Foundation',
                'url': 'https://www.sfari.org/grant-opportunities/',
                'deadlines': self.generate_recurring_deadlines(['January 15', 'July 15']),
                'amounts': [100000, 300000],
                'description': 'Research grants focused on autism spectrum disorders.',
                'last_updated': datetime.now(),
                'source_type': 'static',
                'eligibility': ['assistant professor', 'associate professor', 'professor']
            }
        ]

        # Filter by relevance and career stage
        for grant in static_grants:
            if self.is_relevant_grant(grant):
                self.grants.append(grant)

    def generate_recurring_deadlines(self, date_strings):
        """Generate next occurrence of recurring deadlines"""
        deadlines = []
        current_year = datetime.now().year

        for date_str in date_strings:
            try:
                # Try current year first
                deadline = datetime.strptime(f"{date_str} {current_year}", '%B %d %Y')
                if deadline > datetime.now():
                    deadlines.append(deadline)
                else:
                    # Try next year
                    deadline = datetime.strptime(f"{date_str} {current_year + 1}", '%B %d %Y')
                    deadlines.append(deadline)
            except:
                pass

        return deadlines

    def is_relevant_grant(self, grant):
        """Check if grant is relevant to research areas and career stage"""
        text_to_check = (grant['title'] + ' ' + grant.get('description', '')).lower()

        # Check research area relevance
        area_match = any(area in text_to_check for area in self.research_areas)

        # Check career stage eligibility
        eligibility = grant.get('eligibility', [])
        career_match = True  # Default to True if no eligibility specified
        if eligibility:
            career_match = any(stage in self.career_stage or self.career_stage in stage
                             for stage in eligibility)

        # Broad neuroscience keywords
        neuro_keywords = ['brain', 'neural', 'neuroscience', 'cognitive', 'behavior',
                         'fmri', 'eeg', 'imaging', 'psychology', 'psychiatry', 'mental health']
        neuro_match = any(keyword in text_to_check for keyword in neuro_keywords)

        return (area_match or neuro_match) and career_match

    def calculate_urgency(self, grant):
        """Calculate urgency score based on deadlines"""
        if not grant.get('deadlines'):
            return 0

        nearest_deadline = min(grant['deadlines'])
        days_until = (nearest_deadline - datetime.now()).days

        if days_until <= 30:
            return 5  # Critical
        elif days_until <= 90:
            return 4  # High
        elif days_until <= 180:
            return 3  # Medium
        elif days_until <= 365:
            return 2  # Low
        else:
            return 1  # Very low

    def load_existing_grants(self):
        """Load existing grants from JSON file"""
        grants_file = Path('grant_docs/grants.json')
        if grants_file.exists():
            try:
                with open(grants_file, 'r') as f:
                    data = json.load(f)
                    # Convert date strings back to datetime objects
                    for grant in data:
                        if grant.get('deadlines'):
                            grant['deadlines'] = [
                                datetime.fromisoformat(d.replace('Z', '+00:00'))
                                if isinstance(d, str) else d
                                for d in grant['deadlines']
                            ]
                        if grant.get('last_updated'):
                            grant['last_updated'] = datetime.fromisoformat(
                                grant['last_updated'].replace('Z', '+00:00')
                            )
                    return data
            except Exception as e:
                print(f"Error loading existing grants: {e}")
                return []
        return []

    def save_grants(self):
        """Save grants to JSON file"""
        # Ensure docs directory exists
        Path('grant_docs').mkdir(exist_ok=True)

        # Prepare grants for JSON serialization
        grants_serializable = []
        for grant in self.grants:
            grant_copy = grant.copy()
            if grant_copy.get('deadlines'):
                grant_copy['deadlines'] = [
                    d.isoformat() if isinstance(d, datetime) else d
                    for d in grant_copy['deadlines']
                ]
            if isinstance(grant_copy.get('last_updated'), datetime):
                grant_copy['last_updated'] = grant_copy['last_updated'].isoformat()
            grants_serializable.append(grant_copy)

        with open('grant_docs/grants.json', 'w') as f:
            json.dump(grants_serializable, f, indent=2, default=str)

    def generate_html_website(self):
        """Generate the main HTML website"""
        # Sort grants by urgency and deadline
        grants_with_urgency = []
        for grant in self.grants:
            grant['urgency'] = self.calculate_urgency(grant)
            grants_with_urgency.append(grant)

        sorted_grants = sorted(grants_with_urgency,
                             key=lambda x: (x['urgency'], min(x.get('deadlines', [datetime.max]))),
                             reverse=True)

        # Group by urgency
        urgent_grants = [g for g in sorted_grants if g['urgency'] >= 4]
        upcoming_grants = [g for g in sorted_grants if 2 <= g['urgency'] < 4]
        future_grants = [g for g in sorted_grants if g['urgency'] < 2]

        html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>💰 Grant Deadline Tracker</title>
    <link rel="alternate" type="application/rss+xml" title="Grant Deadlines RSS" href="grants_feed.xml">
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}

        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', system-ui, sans-serif;
            line-height: 1.6;
            color: #333;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
        }}

        .container {{
            max-width: 1200px;
            margin: 0 auto;
            padding: 20px;
        }}

        .header {{
            background: rgba(255, 255, 255, 0.95);
            backdrop-filter: blur(10px);
            border-radius: 20px;
            padding: 30px;
            margin-bottom: 30px;
            text-align: center;
            box-shadow: 0 8px 32px rgba(0, 0, 0, 0.1);
        }}

        .header h1 {{
            font-size: 2.5rem;
            margin-bottom: 10px;
            background: linear-gradient(45deg, #667eea, #764ba2);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            background-clip: text;
        }}

        .stats {{
            display: flex;
            justify-content: center;
            gap: 30px;
            flex-wrap: wrap;
            margin-top: 20px;
        }}

        .stat {{
            text-align: center;
        }}

        .stat-number {{
            font-size: 2rem;
            font-weight: bold;
            color: #667eea;
        }}

        .stat-label {{
            color: #666;
            font-size: 0.9rem;
        }}

        .controls {{
            background: rgba(255, 255, 255, 0.95);
            backdrop-filter: blur(10px);
            border-radius: 15px;
            padding: 20px;
            margin-bottom: 30px;
            display: flex;
            justify-content: space-between;
            align-items: center;
            flex-wrap: wrap;
            gap: 15px;
            box-shadow: 0 4px 16px rgba(0, 0, 0, 0.1);
        }}

        .search-box {{
            flex: 1;
            min-width: 300px;
        }}

        .search-box input {{
            width: 100%;
            padding: 12px 20px;
            border: 2px solid #e1e5e9;
            border-radius: 25px;
            font-size: 1rem;
            transition: all 0.3s ease;
        }}

        .search-box input:focus {{
            outline: none;
            border-color: #667eea;
            box-shadow: 0 0 0 3px rgba(102, 126, 234, 0.1);
        }}

        .filter-buttons {{
            display: flex;
            gap: 10px;
            flex-wrap: wrap;
        }}

        .filter-btn {{
            padding: 8px 16px;
            border: 2px solid #667eea;
            background: white;
            color: #667eea;
            border-radius: 20px;
            cursor: pointer;
            transition: all 0.3s ease;
            text-decoration: none;
        }}

        .filter-btn.active {{
            background: #667eea;
            color: white;
        }}

        .rss-link {{
            background: #ff6b6b;
            color: white;
            padding: 12px 24px;
            border-radius: 25px;
            text-decoration: none;
            font-weight: 500;
            transition: all 0.3s ease;
        }}

        .rss-link:hover {{
            background: #ff5252;
            transform: translateY(-2px);
        }}

        .section {{
            margin-bottom: 40px;
        }}

        .section-header {{
            background: rgba(255, 255, 255, 0.9);
            padding: 20px 25px;
            border-radius: 15px;
            margin-bottom: 20px;
            font-size: 1.4rem;
            font-weight: 600;
            box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
            display: flex;
            justify-content: space-between;
            align-items: center;
        }}

        .urgent {{ color: #ff4444; }}
        .upcoming {{ color: #ff9800; }}
        .future {{ color: #4CAF50; }}

        .grant {{
            background: rgba(255, 255, 255, 0.95);
            backdrop-filter: blur(10px);
            border-radius: 15px;
            padding: 25px;
            margin-bottom: 20px;
            box-shadow: 0 4px 16px rgba(0, 0, 0, 0.1);
            transition: all 0.3s ease;
            border-left: 4px solid #4CAF50;
        }}

        .grant:hover {{
            transform: translateY(-2px);
            box-shadow: 0 8px 32px rgba(0, 0, 0, 0.15);
        }}

        .grant.urgent {{
            border-left-color: #ff4444;
        }}

        .grant.upcoming {{
            border-left-color: #ff9800;
        }}

        .grant-title {{
            font-size: 1.3rem;
            font-weight: bold;
            color: #333;
            margin-bottom: 10px;
            line-height: 1.4;
        }}

        .grant-title a {{
            color: inherit;
            text-decoration: none;
        }}

        .grant-title a:hover {{
            color: #667eea;
        }}

        .grant-meta {{
            display: flex;
            gap: 20px;
            margin-bottom: 15px;
            flex-wrap: wrap;
        }}

        .agency {{
            color: #667eea;
            font-weight: 500;
        }}

        .amount {{
            color: #4CAF50;
            font-weight: 500;
        }}

        .description {{
            color: #555;
            line-height: 1.6;
            margin-bottom: 15px;
        }}

        .deadlines {{
            background: #f8f9fa;
            padding: 15px;
            border-radius: 10px;
            margin-bottom: 15px;
        }}

        .deadline {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            padding: 8px 0;
            border-bottom: 1px solid #eee;
        }}

        .deadline:last-child {{
            border-bottom: none;
        }}

        .deadline-date {{
            font-weight: bold;
        }}

        .deadline-countdown {{
            font-size: 0.9rem;
            padding: 4px 8px;
            border-radius: 8px;
            color: white;
        }}

        .countdown-critical {{ background: #ff4444; }}
        .countdown-warning {{ background: #ff9800; }}
        .countdown-ok {{ background: #4CAF50; }}

        .eligibility {{
            display: flex;
            gap: 5px;
            flex-wrap: wrap;
            margin-top: 10px;
        }}

        .eligibility-tag {{
            background: #e3f2fd;
            color: #1976d2;
            padding: 4px 8px;
            border-radius: 12px;
            font-size: 0.8rem;
        }}

        .footer {{
            background: rgba(255, 255, 255, 0.9);
            backdrop-filter: blur(10px);
            border-radius: 15px;
            padding: 20px;
            text-align: center;
            margin-top: 40px;
            color: #666;
            box-shadow: 0 4px 16px rgba(0, 0, 0, 0.1);
        }}

        .empty-state {{
            background: rgba(255, 255, 255, 0.9);
            backdrop-filter: blur(10px);
            border-radius: 15px;
            padding: 40px;
            text-align: center;
            color: #666;
            box-shadow: 0 4px 16px rgba(0, 0, 0, 0.1);
        }}

        @media (max-width: 768px) {{
            .container {{ padding: 10px; }}
            .header {{ padding: 20px; }}
            .header h1 {{ font-size: 2rem; }}
            .controls {{ flex-direction: column; }}
            .grant {{ padding: 20px; }}
            .grant-meta {{ flex-direction: column; gap: 10px; }}
            .deadline {{ flex-direction: column; align-items: flex-start; gap: 5px; }}
        }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>💰 Grant Deadline Tracker</h1>
            <p class="subtitle">Never miss a funding opportunity • Last updated: {datetime.now().strftime('%Y-%m-%d %H:%M UTC')}</p>
            <div class="stats">
                <div class="stat">
                    <div class="stat-number">{len(urgent_grants)}</div>
                    <div class="stat-label">Urgent (≤90 days)</div>
                </div>
                <div class="stat">
                    <div class="stat-number">{len(upcoming_grants)}</div>
                    <div class="stat-label">Upcoming (3-6 months)</div>
                </div>
                <div class="stat">
                    <div class="stat-number">{len(future_grants)}</div>
                    <div class="stat-label">Future (6+ months)</div>
                </div>
                <div class="stat">
                    <div class="stat-number">{len(sorted_grants)}</div>
                    <div class="stat-label">Total Opportunities</div>
                </div>
            </div>
        </div>

        <div class="controls">
            <div class="search-box">
                <input type="text" id="searchInput" placeholder="🔍 Search grants by title, agency, or description...">
            </div>
            <div class="filter-buttons">
                <button class="filter-btn active" data-filter="all">All</button>
                <button class="filter-btn" data-filter="urgent">Urgent</button>
                <button class="filter-btn" data-filter="upcoming">Upcoming</button>
                <button class="filter-btn" data-filter="future">Future</button>
            </div>
            <a href="grants_feed.xml" class="rss-link">📡 RSS Feed</a>
        </div>

        <div id="grantsContainer">"""

        # Add urgent grants section
        if urgent_grants:
            html += f"""
            <div class="section" data-section="urgent">
                <div class="section-header urgent">
                    🚨 Urgent Deadlines ({len(urgent_grants)} grants)
                    <span style="font-size: 0.9rem; font-weight: normal;">≤90 days remaining</span>
                </div>
                {self.render_grants_html(urgent_grants, 'urgent')}
            </div>"""

        # Add upcoming grants section
        if upcoming_grants:
            html += f"""
            <div class="section" data-section="upcoming">
                <div class="section-header upcoming">
                    ⏰ Upcoming Deadlines ({len(upcoming_grants)} grants)
                    <span style="font-size: 0.9rem; font-weight: normal;">3-6 months</span>
                </div>
                {self.render_grants_html(upcoming_grants, 'upcoming')}
            </div>"""

        # Add future grants section
        if future_grants:
            html += f"""
            <div class="section" data-section="future">
                <div class="section-header future">
                    📅 Future Opportunities ({len(future_grants)} grants)
                    <span style="font-size: 0.9rem; font-weight: normal;">6+ months</span>
                </div>
                {self.render_grants_html(future_grants, 'future')}
            </div>"""

        if not sorted_grants:
            html += """
            <div class="empty-state">
                <h3>No grants found</h3>
                <p>Check your research areas configuration or try again later.</p>
            </div>"""

        html += """
        </div>

        <div class="footer">
            <p>🤖 Generated automatically by GitHub Actions Grant Tracker</p>
            <p>Data sources: NIH, NSF, Brain & Behavior Research Foundation, Simons Foundation</p>
            <p><strong>⚠️ Always verify deadlines on official websites before applying</strong></p>
        </div>
    </div>

    <script>
        // Search functionality
        const searchInput = document.getElementById('searchInput');
        const grantsContainer = document.getElementById('grantsContainer');
        const allGrants = document.querySelectorAll('.grant');
        const filterButtons = document.querySelectorAll('.filter-btn');

        let currentFilter = 'all';

        searchInput.addEventListener('input', function() {
            filterGrants();
        });

        filterButtons.forEach(btn => {
            btn.addEventListener('click', function() {
                filterButtons.forEach(b => b.classList.remove('active'));
                this.classList.add('active');
                currentFilter = this.getAttribute('data-filter');
                filterGrants();
            });
        });

        function filterGrants() {
            const searchTerm = searchInput.value.toLowerCase();

            allGrants.forEach(grant => {
                const searchableText = grant.getAttribute('data-searchable');
                const grantSection = grant.getAttribute('data-urgency');

                const matchesSearch = searchableText.includes(searchTerm);
                const matchesFilter = currentFilter === 'all' || grantSection === currentFilter;

                grant.style.display = (matchesSearch && matchesFilter) ? 'block' : 'none';
            });

            // Show/hide sections based on visible grants
            document.querySelectorAll('.section').forEach(section => {
                const sectionType = section.getAttribute('data-section');
                const visibleGrants = section.querySelectorAll('.grant[style*="block"], .grant:not([style*="none"])');

                if (currentFilter === 'all' || currentFilter === sectionType) {
                    section.style.display = visibleGrants.length > 0 ? 'block' : 'none';
                } else {
                    section.style.display = 'none';
                }
            });
        }

        // Auto-update countdowns
        function updateCountdowns() {
            document.querySelectorAll('.deadline-countdown').forEach(countdown => {
                const deadlineStr = countdown.getAttribute('data-deadline');
                const deadline = new Date(deadlineStr);
                const now = new Date();
                const diffTime = deadline - now;
                const diffDays = Math.ceil(diffTime / (1000 * 60 * 60 * 24));

                if (diffDays <= 0) {
                    countdown.textContent = 'EXPIRED';
                    countdown.className = 'deadline-countdown countdown-critical';
                } else if (diffDays <= 30) {
                    countdown.textContent = diffDays + ' days';
                    countdown.className = 'deadline-countdown countdown-critical';
                } else if (diffDays <= 90) {
                    countdown.textContent = diffDays + ' days';
                    countdown.className = 'deadline-countdown countdown-warning';
                } else {
                    countdown.textContent = diffDays + ' days';
                    countdown.className = 'deadline-countdown countdown-ok';
                }
            });
        }

        // Update countdowns every minute
        updateCountdowns();
        setInterval(updateCountdowns, 60000);
    </script>
</body>
</html>"""

        return html

    def render_grants_html(self, grants, urgency_class):
        """Render HTML for a list of grants"""
        html = ""

        for grant in grants:
            amount_str = ""
            if grant.get('amounts'):
                min_amount = min(grant['amounts'])
                max_amount = max(grant['amounts'])
                if min_amount == max_amount:
                    amount_str = f"${min_amount:,}"
                else:
                    amount_str = f"${min_amount:,} - ${max_amount:,}"

            deadlines_html = ""
            if grant.get('deadlines'):
                deadlines_html = '<div class="deadlines"><strong>📅 Deadlines:</strong>'
                for deadline in sorted(grant['deadlines']):
                    days_until = (deadline - datetime.now()).days
                    deadline_str = deadline.strftime('%B %d, %Y')
                    deadlines_html += f"""
                    <div class="deadline">
                        <span class="deadline-date">{deadline_str}</span>
                        <span class="deadline-countdown" data-deadline="{deadline.isoformat()}">{days_until} days</span>
                    </div>"""
                deadlines_html += '</div>'

            eligibility_html = ""
            if grant.get('eligibility'):
                eligibility_html = '<div class="eligibility">'
                for tag in grant['eligibility']:
                    eligibility_html += f'<span class="eligibility-tag">{tag}</span>'
                eligibility_html += '</div>'

            searchable_text = (grant['title'] + ' ' + grant['agency'] + ' ' +
                             grant.get('description', '')).lower()

            html += f"""
            <div class="grant {urgency_class}" data-urgency="{urgency_class}"
                 data-searchable="{searchable_text}">
                <div class="grant-title">
                    <a href="{grant['url']}" target="_blank">{grant['title']}</a>
                </div>
                <div class="grant-meta">
                    <div class="agency">🏛️ {grant['agency']}</div>
                    {f'<div class="amount">💰 {amount_str}</div>' if amount_str else ''}
                </div>
                <div class="description">{grant.get('description', 'No description available.')}</div>
                {deadlines_html}
                {eligibility_html}
            </div>"""

        return html

    def generate_rss_feed(self):
        """Generate RSS feed for grant deadlines"""
        # Sort by urgency and deadline
        sorted_grants = sorted(self.grants,
                             key=lambda x: (x.get('urgency', 0), min(x.get('deadlines', [datetime.max]))),
                             reverse=True)

        rss_xml = f"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0" xmlns:atom="http://www.w3.org/2005/Atom">
<channel>
    <title>💰 Grant Deadline Tracker</title>
    <description>Automated tracking of neuroscience funding opportunities and deadlines</description>
    <link>https://{os.getenv('GITHUB_REPOSITORY', 'username/repo').split('/')[0]}.github.io/{os.getenv('GITHUB_REPOSITORY', 'username/repo').split('/')[1]}/</link>
    <atom:link href="https://{os.getenv('GITHUB_REPOSITORY', 'username/repo').split('/')[0]}.github.io/{os.getenv('GITHUB_REPOSITORY', 'username/repo').split('/')[1]}/grants_feed.xml" rel="self" type="application/rss+xml"/>
    <lastBuildDate>{datetime.now().strftime('%a, %d %b %Y %H:%M:%S +0000')}</lastBuildDate>
    <language>en-us</language>
    <generator>GitHub Actions Grant Deadline Tracker</generator>
"""

        for grant in sorted_grants[:30]:  # Latest 30 grants
            urgency_emoji = "🚨" if grant.get('urgency', 0) >= 4 else "⏰" if grant.get('urgency', 0) >= 2 else "📅"

            deadlines_text = ""
            if grant.get('deadlines'):
                deadline_list = [d.strftime('%B %d, %Y') for d in grant['deadlines']]
                deadlines_text = "Deadlines: " + ", ".join(deadline_list)

            amounts_text = ""
            if grant.get('amounts'):
                min_amount = min(grant['amounts'])
                max_amount = max(grant['amounts'])
                if min_amount == max_amount:
                    amounts_text = f"Award: ${min_amount:,}"
                else:
                    amounts_text = f"Award: ${min_amount:,} - ${max_amount:,}"

            # Clean for XML
            clean_title = grant['title'].replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
            clean_description = grant.get('description', '').replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')

            pub_date = grant.get('last_updated', datetime.now()).strftime('%a, %d %b %Y %H:%M:%S +0000')

            rss_xml += f"""
    <item>
        <title>{urgency_emoji} {clean_title}</title>
        <description><![CDATA[
            <p><strong>Agency:</strong> {grant['agency']}</p>
            {f'<p><strong>{amounts_text}</strong></p>' if amounts_text else ''}
            {f'<p><strong>{deadlines_text}</strong></p>' if deadlines_text else ''}
            <hr>
            <p>{clean_description}</p>
        ]]></description>
        <link>{grant['url']}</link>
        <guid>{hash(grant['title'] + grant['agency'])}</guid>
        <pubDate>{pub_date}</pubDate>
    </item>"""

        rss_xml += """
</channel>
</rss>"""

        return rss_xml

    def run(self):
        """Main execution function"""
        print("Starting Grant Deadline Tracker...")

        # Load existing grants
        if os.getenv('FORCE_REFRESH', 'false').lower() != 'true':
            existing_grants = self.load_existing_grants()
            # Only keep grants updated in the last 7 days to force refresh of old data
            week_ago = datetime.now() - timedelta(days=7)
            self.grants = [g for g in existing_grants
                          if g.get('last_updated', datetime.min) > week_ago]
            print(f"Loaded {len(self.grants)} existing grants")

        # Scrape new data
        self.scrape_static_opportunities()  # Always include known opportunities
        self.scrape_nih_grants()
        self.scrape_nsf_grants()
        self.scrape_foundation_grants()

        # Remove duplicates based on title and agency
        unique_grants = {}
        for grant in self.grants:
            key = (grant['title'].lower().strip(), grant['agency'].lower())
            if key not in unique_grants or grant.get('last_updated', datetime.min) > unique_grants[key].get('last_updated', datetime.min):
                unique_grants[key] = grant

        self.grants = list(unique_grants.values())
        print(f"Total unique grants found: {len(self.grants)}")

        # Calculate urgency for all grants
        for grant in self.grants:
            grant['urgency'] = self.calculate_urgency(grant)

        # Generate website and RSS
        print("Generating website...")
        html_content = self.generate_html_website()

        print("Generating RSS feed...")
        rss_content = self.generate_rss_feed()

        # Save everything
        self.save_grants()

        # Write HTML file
        with open('grant_docs/index.html', 'w') as f:
            f.write(html_content)

        # Write RSS feed
        with open('grant_docs/grants_feed.xml', 'w') as f:
            f.write(rss_content)

        # Generate a simple calendar view
        self.generate_calendar_view()

        print("Grant tracking complete!")
        print(f"Website will be available at: https://{os.getenv('GITHUB_REPOSITORY', 'username/repo').split('/')[0]}.github.io/{os.getenv('GITHUB_REPOSITORY', 'username/repo').split('/')[1]}/")

    def generate_calendar_view(self):
        """Generate a calendar view of upcoming deadlines"""
        # Group deadlines by month
        deadlines_by_month = {}

        for grant in self.grants:
            for deadline in grant.get('deadlines', []):
                month_key = deadline.strftime('%Y-%m')
                if month_key not in deadlines_by_month:
                    deadlines_by_month[month_key] = []
                deadlines_by_month[month_key].append({
                    'date': deadline,
                    'grant': grant
                })

        # Generate simple calendar HTML
        calendar_html = """<!DOCTYPE html>
<html>
<head>
    <title>Grant Calendar View</title>
    <style>
        body { font-family: Arial, sans-serif; margin: 20px; }
        .month { margin-bottom: 30px; border: 1px solid #ddd; border-radius: 8px; }
        .month-header { background: #667eea; color: white; padding: 15px; font-size: 1.2rem; }
        .deadline-item { padding: 10px; border-bottom: 1px solid #eee; }
        .deadline-date { font-weight: bold; color: #333; }
        .grant-title { color: #667eea; margin-left: 10px; }
    </style>
</head>
<body>
    <h1>📅 Grant Deadlines Calendar</h1>
"""

        for month_key in sorted(deadlines_by_month.keys()):
            month_name = datetime.strptime(month_key, '%Y-%m').strftime('%B %Y')
            calendar_html += f"""
    <div class="month">
        <div class="month-header">{month_name}</div>
"""

            # Sort deadlines by date
            month_deadlines = sorted(deadlines_by_month[month_key], key=lambda x: x['date'])

            for item in month_deadlines:
                deadline_str = item['date'].strftime('%d')
                calendar_html += f"""
        <div class="deadline-item">
            <span class="deadline-date">{deadline_str}</span>
            <span class="grant-title">{item['grant']['title']} ({item['grant']['agency']})</span>
        </div>"""

            calendar_html += "</div>"

        calendar_html += """
</body>
</html>"""

        with open('grant_docs/calendar.html', 'w') as f:
            f.write(calendar_html)

def main():
    """Main function"""
    tracker = GrantTracker()
    tracker.run()

if __name__ == "__main__":
    main()