import re
import requests
from bs4 import BeautifulSoup
from urllib.parse import quote_plus
import json

class IMDb:
    def __init__(self):
        self.base_url = "https://www.imdb.com"
        self.search_url = f"{self.base_url}/find?q="
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/121.0.0.0'
        }

    def _match_score(self, query, title):
        """Calculate how well a search result matches the query"""
        query = query.lower()
        title = title.lower()
        
        # Exact match gets highest score
        if query == title:
            return 100
            
        # Remove common words that might interfere with matching
        common_words = {'the', 'a', 'an', 'and', '&'}
        query_words = set(word for word in query.split() if word not in common_words)
        title_words = set(word for word in title.split() if word not in common_words)
        
        # Calculate word overlap
        matching_words = query_words & title_words
        total_query_words = len(query_words)
        
        if not matching_words:
            return 0
            
        # Calculate match percentage
        match_percentage = (len(matching_words) / total_query_words) * 100
        
        # Add bonus for words in same order
        if all(word in title for word in query.split()):
            match_percentage += 20
            
        return match_percentage

    def search_movie(self, query):
        """Search for movies on IMDB"""
        url = self.search_url + quote_plus(query) + "&s=tt"
        response = requests.get(url, headers=self.headers)
        soup = BeautifulSoup(response.text, 'html.parser')
        
        results = []
        for item in soup.select('.ipc-metadata-list-summary-item'):
            try:
                title_elem = item.select_one('.ipc-metadata-list-summary-item__t')
                if not title_elem:
                    continue
                    
                link = title_elem.get('href', '')
                imdb_id = re.search(r'/title/(tt\d+)/', link)
                if not imdb_id:
                    continue
                    
                title = title_elem.text
                # Calculate match score
                match_score = self._match_score(query, title)
                
                # Only include results with good match scores
                if match_score >= 70:  # Require at least 70% match
                    year_elem = item.select_one('.ipc-metadata-list-summary-item__year')
                    year = year_elem.text if year_elem else ''
                    
                    results.append({
                        'movieID': imdb_id.group(1),
                        'title': title,
                        'year': year,
                        'url': f"{self.base_url}{link}",
                        'match_score': match_score
                    })
            except Exception as e:
                print(f"Error parsing search result: {e}")
                continue
        
        # Sort by match score and return best matches only
        results.sort(key=lambda x: x['match_score'], reverse=True)
        return results[:5] if results else None  # Return top 5 matches or None if no good matches

    def search_tv(self, query):
        """Search for TV shows on IMDB"""
        url = self.search_url + quote_plus(query) + "&s=tt&ttype=tv"
        response = requests.get(url, headers=self.headers)
        soup = BeautifulSoup(response.text, 'html.parser')
        
        results = []
        for item in soup.select('.ipc-metadata-list-summary-item'):
            try:
                title_elem = item.select_one('.ipc-metadata-list-summary-item__t')
                if not title_elem:
                    continue
                    
                link = title_elem.get('href', '')
                imdb_id = re.search(r'/title/(tt\d+)/', link)
                if not imdb_id:
                    continue
                    
                year_elem = item.select_one('.ipc-metadata-list-summary-item__year')
                year = year_elem.text if year_elem else ''
                
                results.append({
                    'seriesID': imdb_id.group(1),
                    'title': title_elem.text,
                    'year': year,
                    'url': f"{self.base_url}{link}"
                })
            except Exception as e:
                print(f"Error parsing TV search result: {e}")
                continue
                
        return results

    def get_movie(self, movie_id):
        """Get detailed information about a movie"""
        url = f"{self.base_url}/title/{movie_id}/"
        response = requests.get(url, headers=self.headers)
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Extract JSON-LD data
        script = soup.find('script', {'type': 'application/ld+json'})
        if not script:
            return None
            
        try:
            import json
            data = json.loads(script.string)
            
            # Try to extract a longer plot summary from the page
            long_plot_elem = soup.find('span', {'data-testid': 'plot-xl'})
            if long_plot_elem and long_plot_elem.text.strip():
                plot = long_plot_elem.text.strip()
            else:
                plot = data.get('description', '')
            
            # Fetch cast images
            cast_nodes = soup.select('div[data-testid="title-cast-item"]')
            cast_with_images = []
            actors = data.get('actor', [])  # may be list or single dict
            if not isinstance(actors, list):
                actors = [actors]
            for i, actor in enumerate(actors[:5]):
                image_url = None
                if i < len(cast_nodes):
                    img = cast_nodes[i].find('img')
                    if img:
                        image_url = img.get('src')
                cast_with_images.append({
                    'name': actor.get('name', ''),
                    'image': image_url
                })
                
            # Fetch director images (if available)
            # Attempt to find director nodes by looking in the principal credit section
            director_nodes = soup.select('div[data-testid="title-pc-principal-credit"] a[href*="/name/"]')
            directors = data.get('director', [])
            if not isinstance(directors, list):
                directors = [directors]
            director_with_images = []
            for i, director in enumerate(directors):
                image_url = None
                if i < len(director_nodes):
                    dir_img = director_nodes[i].find('img')
                    if dir_img:
                        image_url = dir_img.get('src')
                director_with_images.append({
                    'name': director.get('name', ''),
                    'image': image_url
                })
            
            return {
                'title': data.get('name', ''),
                'plot outline': plot,  # Use the longer plot text if available
                'full-size cover url': data.get('image', ''),
                'rating': data.get('aggregateRating', {}).get('ratingValue'),
                'directors': director_with_images,
                'cast': cast_with_images,
                'year': data.get('datePublished', '')[:4],
                'genres': data.get('genre', [])
            }
        except Exception as e:
            print(f"Error parsing movie data: {e}")
            return None

    def get_show(self, show_id):
        """Get detailed information about a TV show"""
        url = f"{self.base_url}/title/{show_id}/"
        response = requests.get(url, headers=self.headers)
        soup = BeautifulSoup(response.text, 'html.parser')
        
        script = soup.find('script', {'type': 'application/ld+json'})
        if not script:
            return None
            
        try:
            data = json.loads(script.string)
            
            # Get longer plot if available
            long_plot_elem = soup.find('span', {'data-testid': 'plot-xl'})
            plot = long_plot_elem.text.strip() if long_plot_elem else data.get('description', '')
            
            # Get number of seasons
            season_count_elem = soup.select_one('[data-testid="episodes-header"] span')
            num_seasons = int(re.search(r'\d+', season_count_elem.text).group()) if season_count_elem else 0
            
            # Fetch cast images
            cast_nodes = soup.select('div[data-testid="title-cast-item"]')
            cast_with_images = []
            actors = data.get('actor', [])
            if not isinstance(actors, list):
                actors = [actors]
            for i, actor in enumerate(actors[:10]):  # Get top 10 cast members
                image_url = None
                if i < len(cast_nodes):
                    img = cast_nodes[i].find('img')
                    if img:
                        image_url = img.get('src')
                cast_with_images.append({
                    'name': actor.get('name', ''),
                    'image': image_url
                })
            
            # Fetch creator images
            creator_nodes = soup.select('div[data-testid="title-pc-principal-credit"] a[href*="/name/"]')
            creators = data.get('creator', [])
            if not isinstance(creators, list):
                creators = [creators]
            creator_with_images = []
            for i, creator in enumerate(creators):
                image_url = None
                if i < len(creator_nodes):
                    cr_img = creator_nodes[i].find('img')
                    if cr_img:
                        image_url = cr_img.get('src')
                creator_with_images.append({
                    'name': creator.get('name', ''),
                    'image': image_url
                })
            
            return {
                'title': data.get('name', ''),
                'plot outline': plot,
                'full-size cover url': data.get('image', ''),
                'rating': data.get('aggregateRating', {}).get('ratingValue'),
                'creators': creator_with_images,
                'cast': cast_with_images,
                'year': data.get('datePublished', '')[:4],
                'genres': data.get('genre', []),
                'number of seasons': num_seasons
            }
        except Exception as e:
            print(f"Error parsing show data: {e}")
            return None

    def get_season(self, show_id, season_number):
        """Get episode information for a specific season"""
        url = f"{self.base_url}/title/{show_id}/episodes?season={season_number}"
        response = requests.get(url, headers=self.headers)
        soup = BeautifulSoup(response.text, 'html.parser')
        
        episodes = []
        episode_nodes = soup.select('div.episode-item-wrapper')
        
        for node in episode_nodes:
            try:
                # Get episode title
                title_elem = node.select_one('.ipc-title__text')
                if not title_elem:
                    continue
                
                # Extract episode number and title
                # Format is usually "S1, Ep2 • Episode Title"
                title_text = title_elem.text.strip()
                ep_parts = title_text.split('•')
                if len(ep_parts) >= 2:
                    # Get episode number
                    ep_num_match = re.search(r'Ep(\d+)', ep_parts[0])
                    ep_num = int(ep_num_match.group(1)) if ep_num_match else 0
                    # Get clean episode title
                    ep_title = ep_parts[1].strip()
                else:
                    # Fallback if format is different
                    ep_num = 0
                    ep_title = title_text
                
                # Get plot
                plot_elem = node.select_one('.ipc-html-content-inner-div')
                plot = plot_elem.text.strip() if plot_elem else ''
                
                # Get air date
                air_date_elem = node.select_one('.episode-air-date')
                air_date = air_date_elem.text.strip() if air_date_elem else ''
                
                # Get rating
                rating_elem = node.select_one('.ipc-rating-star--imdb')
                rating = rating_elem.text.split()[0] if rating_elem else None
                
                episodes.append({
                    'title': ep_title,
                    'episode_title': ep_title,  # Add specific episode title field
                    'episode_number': ep_num,
                    'plot': plot,
                    'original air date': air_date,
                    'rating': rating
                })
                
            except Exception as e:
                print(f"Error parsing episode data: {e}")
                continue
        
        return {
            'season_number': season_number,
            'episodes': sorted(episodes, key=lambda x: x['episode_number'])
        }

    def search_person(self, name):
        """Search for a person on IMDb"""
        url = self.search_url + quote_plus(name) + "&s=nm"  # nm indicates name search
        response = requests.get(url, headers=self.headers)
        soup = BeautifulSoup(response.text, 'html.parser')
        
        results = []
        for item in soup.select('.ipc-metadata-list-summary-item'):
            try:
                title_elem = item.select_one('.ipc-metadata-list-summary-item__t')
                if not title_elem:
                    continue
                    
                link = title_elem.get('href', '')
                person_id = re.search(r'/name/(nm\d+)/', link)
                if not person_id:
                    continue
                    
                name_text = title_elem.text
                match_score = self._match_score(name, name_text)
                
                if match_score >= 70:  # Require at least 70% match
                    profession_elem = item.select_one('.ipc-metadata-list-summary-item__subtext')
                    profession = profession_elem.text if profession_elem else ''
                    
                    results.append({
                        'personID': person_id.group(1),
                        'name': name_text,
                        'profession': profession,
                        'url': f"{self.base_url}{link}",
                        'match_score': match_score
                    })
            except Exception as e:
                print(f"Error parsing person search result: {e}")
                continue
        
        # Sort by match score and return best matches
        results.sort(key=lambda x: x['match_score'], reverse=True)
        return results[:5] if results else None

    def get_person(self, person_id):
        """Get detailed information about a person"""
        url = f"{self.base_url}/name/{person_id}/"
        response = requests.get(url, headers=self.headers)
        soup = BeautifulSoup(response.text, 'html.parser')
        
        script = soup.find('script', {'type': 'application/ld+json'})
        if not script:
            return None
            
        try:
            data = json.loads(script.string)
            
            # Get bio if available
            bio_elem = soup.select_one('[data-testid="biography"]')
            bio = bio_elem.text.strip() if bio_elem else data.get('description', '')
            
            # Get headshot
            headshot_elem = soup.select_one('[data-testid="hero-image-details"] img')
            headshot = headshot_elem.get('src') if headshot_elem else data.get('image', '')
            
            return {
                'name': data.get('name', ''),
                'bio': bio,
                'headshot': headshot,
                'birth_date': data.get('birthDate', ''),
                'birth_place': data.get('birthPlace', ''),
                'profession': data.get('jobTitle', '')
            }
        except Exception as e:
            print(f"Error parsing person data: {e}")
            return None

# Example usage:
if __name__ == "__main__":
    imdb = IMDb()
    results = imdb.search_movie("The Matrix")
    if results:
        details = imdb.get_movie(results[0]['movieID'])
        print(json.dumps(details, indent=2))