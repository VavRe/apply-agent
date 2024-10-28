import requests
import logging
import time
import pandas as pd
from typing import List, Dict
from datetime import datetime
import csv
import xml.etree.ElementTree as ET
from urllib.parse import quote
import os
import json
import re

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        # logging.FileHandler(f'author_papers_{datetime.now().strftime("%Y%m%d_%H%M%S")}.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Configuration
BATCH_SIZE = 20
CURRENT_YEAR = datetime.now().year
EARLIEST_YEAR = CURRENT_YEAR - 1
SEMANTIC_SCHOLAR_API_KEY = None  # Optional: Add your key if you have one

class AuthorFetcher:
    def __init__(self):
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
        if SEMANTIC_SCHOLAR_API_KEY:
            self.headers['x-api-key'] = SEMANTIC_SCHOLAR_API_KEY

    
    def get_crossref_abstract(self, title: str, authors: List[str]) -> str:
        """Fetch abstract from Crossref."""
        try:
            # Construct the query using title and first author
            query = f"{title} {authors[0]}"
            url = "https://api.crossref.org/works"
            params = {
                'query': query,
                'select': 'title,abstract',
                'rows': 1
            }
            
            # Add email to headers for better rate limiting from Crossref
            headers = self.headers.copy()
            headers['mailto'] = 'your-email@domain.com'  # Replace with your email
            
            response = requests.get(url, params=params, headers=headers)
            response.raise_for_status()
            data = response.json()
            
            if 'message' in data and 'items' in data['message'] and data['message']['items']:
                item = data['message']['items'][0]
                if 'abstract' in item:
                    # Clean up the abstract (remove HTML tags if present)
                    abstract = re.sub('<[^<]+?>', '', item['abstract'])
                    return abstract.strip()
        except Exception as e:
            logger.error(f"Error fetching Crossref abstract: {str(e)}")
        return ""


    def get_author_info(self, author_name: str) -> Dict:
        """Fetch author information from DBLP."""
        try:
            logger.info(f"Fetching author information for {author_name}...")
            
            # Search for the author
            search_url = f"https://dblp.org/search/author/api?q={quote(author_name)}&format=json"
            response = requests.get(search_url, headers=self.headers)
            response.raise_for_status()
            data = response.json()

            if 'result' in data and 'hits' in data['result']:
                hits = data['result']['hits']
                if 'hit' in hits and hits['hit']:
                    author_info = hits['hit'][0]['info']
                    author_url = author_info.get('url', '')
                    
                    if author_url:
                        api_url = author_url.replace('https://dblp.org/', 'https://dblp.org/pid/').replace('.html', '.xml')
                        response = requests.get(api_url, headers=self.headers)
                        response.raise_for_status()
                        
                        root = ET.fromstring(response.content)
                        
                        author_data = {
                            'name': author_info.get('author', ''),
                            'dblp_url': author_url,
                            'aliases': [name.text for name in root.findall('.//person/names/name')],
                            'affiliations': [note.text for note in root.findall('.//person/notes/note') 
                                           if note.text and 'affiliation' in note.get('type', '').lower()],
                            'homepage': next((url.text for url in root.findall('.//person/notes/url') 
                                           if url.text), ''),
                            'total_publications': len(root.findall('.//r')),
                        }
                        
                        return author_data
            
            logger.warning(f"No detailed information found for {author_name}")
            return {'name': author_name, 'error': 'No detailed information found'}

        except Exception as e:
            logger.error(f"Error fetching author information: {str(e)}")
            return {'name': author_name, 'error': str(e)}

    def get_semantic_scholar_abstract(self, title: str, authors: List[str]) -> str:
        """Fetch abstract from Semantic Scholar."""
        try:
            query = f"{title} {authors[0]}"
            url = f"https://api.semanticscholar.org/graph/v1/paper/search?query={quote(query)}&fields=abstract"
            
            response = requests.get(url, headers=self.headers)
            response.raise_for_status()
            data = response.json()
            
            if 'data' in data and data['data']:
                return data['data'][0].get('abstract', '')
        except Exception as e:
            logger.error(f"Error fetching Semantic Scholar abstract: {str(e)}")
        return ""

    def get_arxiv_abstract(self, arxiv_id: str) -> str:
        """Fetch abstract from arXiv."""
        try:
            url = f"http://export.arxiv.org/api/query?id_list={arxiv_id}"
            response = requests.get(url, headers=self.headers)
            response.raise_for_status()
            
            root = ET.fromstring(response.content)
            namespace = {'arxiv': 'http://www.w3.org/2005/Atom'}
            abstract = root.find('.//arxiv:summary', namespace)
            
            if abstract is not None:
                return abstract.text.strip()
        except Exception as e:
            logger.error(f"Error fetching arXiv abstract: {str(e)}")
        return ""

    def extract_arxiv_id(self, url: str) -> str:
        """Extract arXiv ID from URL."""
        if 'arxiv.org' in url:
            match = re.search(r'(\d+\.\d+)', url)
            if match:
                return match.group(1)
        return ""

    def get_paper_abstract(self, paper: Dict) -> str:
        """Get paper abstract from various sources."""
        abstract = ""

        # Try Semantic Scholar first
        if paper.get('title') and paper.get('authors'):
            abstract = self.get_semantic_scholar_abstract(paper['title'], paper['authors'])
            time.sleep(1)  # Rate limiting
            
            # If Semantic Scholar fails, try Crossref
            if not abstract:
                # logger.info("Semantic Scholar abstract not found, trying Crossref...")
                abstract = self.get_crossref_abstract(paper['title'], paper['authors'])
                time.sleep(1)  # Rate limiting

        # Try arXiv if still no abstract
        if not abstract and paper.get('url'):
            arxiv_id = self.extract_arxiv_id(paper['url'])
            if arxiv_id:
                abstract = self.get_arxiv_abstract(arxiv_id)

        return abstract
    
    def get_dblp_papers(self, author_name: str) -> List[Dict]:
        """Fetch recent papers from DBLP."""
        papers = []
        try:
            logger.info("Fetching papers from DBLP...")
            url = f"https://dblp.org/search/publ/api?q={quote(author_name)}&format=xml&h=1000"
            
            response = requests.get(url, headers=self.headers)
            response.raise_for_status()
            
            root = ET.fromstring(response.content)
            
            total_hits = len(root.findall('.//hit'))
            logger.info(f"Found {total_hits} total papers")

            for i, hit in enumerate(root.findall('.//hit'), 1):
                try:
                    info = hit.find('info')
                    if info is not None:
                        year_elem = info.find('year')
                        if year_elem is not None:
                            year = int(year_elem.text)
                            
                            if year >= EARLIEST_YEAR:
                                logger.info(f"Processing paper {i}/{total_hits} from year {year}")
                                authors = [author.text for author in info.findall('.//author')]
                                paper = {
                                    'title': info.find('title').text if info.find('title') is not None else '',
                                    'year': year,
                                    'venue': info.find('venue').text if info.find('venue') is not None else '',
                                    'authors': authors,
                                    'type': info.find('type').text if info.find('type') is not None else '',
                                    'url': info.find('url').text if info.find('url') is not None else '',
                                }
                                
                                if paper['title']:
                                    # logger.info(f"Fetching abstract for: {paper['title']}")
                                    paper['abstract'] = self.get_paper_abstract(paper)
                                    papers.append(paper)
                                    
                except Exception as e:
                    logger.error(f"Error processing paper {i}: {str(e)}")

        except Exception as e:
            logger.error(f"Error fetching from DBLP: {str(e)}")

        logger.info(f"Found {len(papers)} recent papers")
        return papers

def save_author_info(author_info: Dict, output_dir: str, author_name: str):
    """Save author information to JSON file."""
    try:
        safe_author_name = "".join(x for x in author_name if x.isalnum() or x in (' ', '-', '_')).strip()
        output_file = os.path.join(output_dir, f"author_info_{safe_author_name}.json")
        
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(author_info, f, indent=2, ensure_ascii=False)
        
        logger.info(f"Saved author information to {output_file}")
    except Exception as e:
        logger.error(f"Error saving author information: {str(e)}")

def save_batch(papers: List[Dict], is_first_batch: bool, output_file: str):
    """Save a batch of papers to CSV."""
    try:
        os.makedirs(os.path.dirname(output_file), exist_ok=True)
        
        df = pd.DataFrame(papers)
        df['authors'] = df['authors'].apply(lambda x: ', '.join(x) if isinstance(x, list) else x)
        
        df['year'] = pd.to_numeric(df['year'], errors='coerce')
        df = df.sort_values(['year', 'title'], ascending=[False, True])
        
        mode = 'w' if is_first_batch else 'a'
        header = is_first_batch
        
        df.to_csv(output_file, mode=mode, header=header, index=False, 
                 encoding='utf-8-sig', quoting=csv.QUOTE_ALL)
        logger.info(f"Saved batch of {len(papers)} papers")
    except Exception as e:
        logger.error(f"Error saving batch: {str(e)}")

def get_author_papers_and_info(author_name: str, output_dir: str):
    """Get author information and papers, and save them."""
    fetcher = AuthorFetcher()
    current_batch = []
    is_first_batch = True
    all_papers = set()

    try:
        # Get and save author information
        author_info = fetcher.get_author_info(author_name)
        save_author_info(author_info, output_dir, author_name)

        # Get and save papers
        papers = fetcher.get_dblp_papers(author_name)
        
        safe_author_name = "".join(x for x in author_name if x.isalnum() or x in (' ', '-', '_')).strip()
        papers_output_file = os.path.join(output_dir, f"recent_papers_{safe_author_name}.csv")
        
        for paper in papers:
            paper_key = f"{paper['title'].lower().strip()}_{paper['year']}"
            if paper_key not in all_papers:
                all_papers.add(paper_key)
                current_batch.append(paper)
                
                if len(current_batch) >= BATCH_SIZE:
                    save_batch(current_batch, is_first_batch, papers_output_file)
                    is_first_batch = False
                    current_batch = []

        if current_batch:
            save_batch(current_batch, is_first_batch, papers_output_file)

        logger.info(f"Total unique recent papers found: {len(all_papers)}")

    except Exception as e:
        logger.error(f"Error in main process: {str(e)}")
        if current_batch:
            save_batch(current_batch, is_first_batch, papers_output_file)

def get_and_save_papers(author_name: str = "Azadeh Shakery"):
    """get_and_save_papers function to get and save author information and papers."""
    output_dir = "author_papers"
    
    try:
        logger.info(f"Starting retrieval process for {author_name}...")
        # logger.info(f"Output will be saved to: {output_dir}")
        
        os.makedirs(output_dir, exist_ok=True)
        
        get_author_papers_and_info(author_name, output_dir)
        logger.info("Process completed successfully")
        
    except Exception as e:
        logger.error(f"Main function error: {str(e)}")

# get_and_save_papers()
