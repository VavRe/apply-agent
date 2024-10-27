import pandas as pd
import re
from pathlib import Path

def parse_professor_info(markdown_path):
    """
    Parse professor information from a markdown file and create a DataFrame.
    
    Args:
        markdown_path (str): Path to the markdown file
        
    Returns:
        pandas.DataFrame: DataFrame with columns ['Name', 'Field', 'Webpage']
    """
    # Read the markdown file
    with open(markdown_path, 'r', encoding='utf-8') as file:
        content = file.read()
    
    # Regular expression to match the professor entries
    # Pattern looks for: ##### Name\nField\n[![...](image_url)](webpage_url)
    pattern = r'#{5}\s+([^\n]+)\s*\n([^\n]+)\s*\n\[!\[.*?\]\(.*?\)\]\((.*?)\)'
    
    # Find all matches
    matches = re.finditer(pattern, content)
    
    # Lists to store the extracted information
    professors = []
    fields = []
    webpages = []
    
    # Extract information from each match
    for match in matches:
        professors.append(match.group(1).strip())
        fields.append(match.group(2).strip())
        webpages.append(match.group(3).strip())
    
    # Create DataFrame
    df = pd.DataFrame({
        'Name': professors,
        'Field': fields,
        'Webpage': webpages
    })
    
    return df

def main():
    # Path to the markdown file
    file_path = Path('./imprs_professors.md')
    
    try:
        # Parse the file and create DataFrame
        df = parse_professor_info(file_path)
        
        # Display the first few rows
        print("\nFirst few entries in the DataFrame:")
        print(df.head())
        
        # Save to CSV (optional)
        df.to_csv('professors_info.csv', index=False)
        print("\nData saved to professors_info.csv")
        
        # Print some statistics
        print(f"\nTotal number of professors found: {len(df)}")
        
    except FileNotFoundError:
        print(f"Error: Could not find file at {file_path}")
    except Exception as e:
        print(f"Error occurred while processing the file: {str(e)}")

if __name__ == "__main__":
    main()