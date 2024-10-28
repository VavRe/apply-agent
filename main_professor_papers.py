import pandas as pd 
from tqdm import tqdm 
from get_professor_papers import get_and_save_papers




df = pd.read_csv('professors_info.csv')
    
with tqdm(total=len(df)) as pbar:
    for idx, row in df.iterrows():
        print('Working on professor:', row['Name'])
        get_and_save_papers(row['Name'])
        pbar.update(1)
