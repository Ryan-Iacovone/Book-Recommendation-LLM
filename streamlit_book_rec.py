from functions_book_rec import *
import streamlit as st

st.title("Custom KDL Book Reccomendations!")
st.subheader("Find Your Next Favorite Read!")

# Creating a sidebar with title and explaination
with st.sidebar:
    st.title('KDL Book Reccomendation Copilot Explained:')
    st.write('This LLM is created using the open-source Llama 3 model from Meta.')
    st.write("Llama 3 does not have access to the internet, so book reccomendations might be older.")
    st.write("Simply prompt the LLM for a book or author reccomendation about a specific topic, genre, or time period and KDL Copilot will return a relevant list cross referenced with KDL's database!")

orig_prompt = st.chat_input("What book reccomendations would you like? ")

if orig_prompt:

    with st.chat_message("user"): # nice formating, highlights user input questions! 
        st.write(orig_prompt)

    output1 = input_llm(orig_prompt)

    st.write("LLM ran for inital book recommendations") 

    book_titles = convert_json(output1)

    master_dict = get_author(book_titles)

    st.write("Author information gained from inital books recs using google reads API") 

    book_recs = match_recs(master_dict)

    st.write("Matched provided book information KDL's databse.") 

    # Drops all rows except for the first occurance of every title
    book_recs.drop_duplicates(subset='Title', keep='first', inplace=True)

    # taking the index variable from book_recs and making it into a list for itterating 
    index_list = book_recs['index']

    #initalizing empty dictionary to put specific book and summary data from KDL db in  
    llm_data = {}

    for index in index_list:
        row_data = monster.iloc[index] # Finds the specific row for each index variable saving all info 
        #print(row_data, "\n")
        summary_value = row_data['summary'] # Keep in mind this summary variable from Sheri's dataset is truncated 
        title_value = row_data['title']
        temp_dict = {title_value: summary_value} # updates temp dict into llm_data for each book in our index_list
        llm_data.update(temp_dict)

    output2 = output_llm(llm_data, orig_prompt)

    with st.chat_message("AI"): # nice little formating, adds a robot here lol
        st.write(output2)  
    
    # Saving the LLM output and orginal prompt to a json db 
    dict = {"prompt": orig_prompt, "output": output2}

    resave_json(dict) 