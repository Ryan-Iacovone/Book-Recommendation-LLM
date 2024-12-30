from langchain_community.llms import Ollama
from langchain_core.prompts import ChatPromptTemplate # Prompt templates convert raw user input to better input to the LLM (guide reponse)
from langchain_core.output_parsers import StrOutputParser # original model output is a message but this function parses it to a string (easier to work with)
from langchain_core.messages import HumanMessage, AIMessage # Used to frame history to LLM and retriever
import pandas as pd
import json
import time
import requests
import sys
import os
from filelock import FileLock, Timeout


# LLM that provides a list of book reccomendations (title only) in the format of a python list
def input_llm(orig_prompt):
    model = "llama3" # mistral, llama2, kdl_copilot_llama3, llama3, llama2:13b
    llm = Ollama(model=model, format='json') # how to structure LLM output: https://python.langchain.com/v0.2/docs/how_to/structured_output/

    system = """Your are a helpful librarian AI assistant. You provide relevant book recommendations based on the context of the users input. \
    Output your response in json, structured with only the book title. \
    Include at least 7 relevant  books. \ 

    Here are some examples of proper json output based on an example prompts:

    example_user: I like mystery book, what are some recommendations like that if I just read Louise Penny?
    example_assistant: {{"book_titles": [
        "A Rule Against Murder",
        "The Word is Murder",
        "Bury Your Dead"]}}

    example_user: What books should I read after 1984 by George Orwell??
    example_assistant: {{"book_titles": [
        "Fahrenheit 451",
        "Animal Farm",
        "Brave new world",
        "The Handmaid's Tale",
        "Lord of the Flies",
        "A Clockwork Orange"]}}
    """

    prompt = ChatPromptTemplate.from_messages([  # LLM unreliable for ISBN number but does good for book titles
        ("system", system),
        ("user", "{input}")
    ])

    output_parser = StrOutputParser()
    chain = prompt | llm | output_parser

    output1 = chain.invoke({"input": orig_prompt}) 

    return output1


# Convering the json output of the LLM into a python list function
def convert_json(output1):
    data = json.loads(output1)

    # Extract the list of book titles from the 'book_titles' property
    book_titles = data['book_titles']
    return book_titles



# Now that we have a list of book titles in the form of a python list, provide each title to the google reads API in order to get the author of each book (needed to match book title to title in KDL database)
# Because ISBN number is not a direct match in our comparison dataset, it's difficult to use this API in our dataset each book title would have to be associated with it's various ISBN versions 

# Function that takes list of book titles as input and returns dictionary with book title as keys and author as value
def get_author(titles):
    # Initalize dictionary that will store all API output  
    master_dict = {}
    for title in titles:
        url = f"https://www.googleapis.com/books/v1/volumes?q={title}&maxResults=1"
        response = requests.get(url)
        data = response.json() 
        author = data["items"][0]["volumeInfo"]["authors"][0]
        last_name = author.split(" ")[1]
        #print("Author:", last_name)
        
        # Writing the output from the google reads API into a dict then updating it to master
        temp_dict = {title: last_name}
        master_dict.update(temp_dict)
        #isbn_13 = data["items"][0]["volumeInfo"]["industryIdentifiers"][0]["identifier"]
        #print("ISBN-13:", isbn_13)

        time.sleep(.5) 
    return master_dict

# Loading in the KDL database we're going to compare our LLM reccomendation output against 
monster = pd.read_excel(r'C:\Users\Ryan\Coding Projects\KDL Project\AI PT\LLM book rec\Book db\kdl_report_edited.xlsx')


def match_recs(master_dict):
    # Initialize an empty DataFrame for storing index data
    book_recs = pd.DataFrame(columns=["Title", "Author", "index"])  

    # Use .loc to find and select rows in our KDL database where title and author match the LLM output
    for key, value in master_dict.items():
        
        key_lower = key.lower() # Converts titles from both API and KDL database to lowercase, easier search when finding observational rows 
        monster_title = monster['title'].str.lower()
        
        # Find rows where the lowercase column contains the lowercase search string
        row_indices = monster.loc[monster_title.str.contains(key_lower)].index.tolist()
        if row_indices is not None: # If we a book title matches from the LLM to KDL database then we keep going to find the exact observation   
            for index in row_indices: 
                value_lower = value.lower() # standardize the string casing for both values of authors from our API and KDL databse for easier search 
                monster_author = monster['Author'].str.lower()
                
                if value_lower in monster_author[index]:  # Matches the authors last name we got from the API to find the correct observation in KDL database
                    new_data = pd.DataFrame({
                        "Title": [key],
                        "Author": [value],
                        "index": [index]
                    })
                    book_recs = pd.concat([book_recs, new_data], ignore_index=True)
        else: # Writes in blank index if title string from LLM is not found in KDL database
            new_data = pd.DataFrame({
                "Title": [key],
                "Author": [value],
                "index": [""]
            })
            book_recs = pd.concat([book_recs, new_data], ignore_index=True)
    return book_recs


# For books that are in KDL's database (AKA have am index present in book_recs df) this LLM recommends them in relation to the original question! 
def output_llm(llm_data, orig_prompt):
    model = "llama3" # mistral, llama2, kdl_copilot_llama3, llama3, llama2:13b
    llm = Ollama(model=model, temperature=0)

    system2 = """Your are a helpful librarian AI assistant. You know a lot about books and have great recommendation advice . \
    Given a python dictionary of book titles and their associated summary as extra context, you can provide me with a summary of why those books are great recommendations in relation to the original prompt. \
    If a book in the python dictionary doesn't at all match the themes of the other books in the original prompt or python dictionary ignore that specific book in your output,
    """

    prompt = ChatPromptTemplate.from_messages([
        ("system", system2), 
        ("user", "{input}")
    ])

    output_parser = StrOutputParser()
    chain = prompt | llm | output_parser

    output2 = chain.invoke({"input": f"Given the following python dictionary of book titles and associated summaries: {llm_data}, provide a summary of why those books are great recommendations in relation to the original prompt: {orig_prompt}."})  

    return output2


# Save the outputed response and original question to db

# Function to save the updated address database
def resave_json(dict):
    # Loading in the Address DB, appending the current address results, and then resaves it 
    save_folder = r"C:\Users\Ryan\Coding Projects\KDL Project\AI PT\LLM book rec\outputs"
    file_path = os.path.join(save_folder, 'LLM_Recs_db.json')
    lock_file_path = file_path + '.lock'

    # Ensure the save folder exists
    os.makedirs(save_folder, exist_ok=True)

    lock = FileLock(lock_file_path, timeout=10) 

    try:
        with lock:
            # Load the address database within the lock context
            if os.path.exists(file_path):
                with open(file_path, 'r') as f:
                    rec_db = json.load(f)
            else:
                rec_db = []

            # Append the new entry
            rec_db.append(dict)

            # Save the updated address database
            with open(file_path, 'w') as f:
                json.dump(rec_db, f, indent=4)

            print(f"Results have been saved to '{file_path}'")

    except Timeout:
        print("Another process is currently accessing the file. Please try again later.")
