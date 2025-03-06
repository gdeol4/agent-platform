import streamlit as st
import openai
import json
import requests
from urllib.parse import quote_plus

# Initialize OpenAI client
client = openai.OpenAI(api_key=st.secrets["openai"]["api_key"])

def get_protein_targets(disease: str):
    """Retrieve protein targets for a given disease using GPT-4"""
    print(f"Debug: Starting get_protein_targets for {disease}")
    
    messages = [
        {"role": "system", "content": "You are an expert in biomedical research."},
        {"role": "user", "content": f"List top 10 protein targets for {disease} as JSON array. Output only JSON."}
    ]
    
    try:
        response = client.chat.completions.create(
            model="gpt-4",
            messages=messages,
            temperature=0.7,
            max_tokens=200
        )
        answer = response.choices[0].message.content.strip()
        return json.loads(answer)
    except Exception as e:
        st.error(f"Error: {e}")
        return []

# Add these imports at the TOP of your file (under existing imports)
import requests
from urllib.parse import quote_plus

def safe_protein_name(protein):
    """Extract protein name from either string or dict"""
    if isinstance(protein, dict):
        return str(protein.get('name', protein.get('proteinName', list(protein.values())[0])))
    return str(protein).split()[0].strip('"\'')  # Take first word and remove quotes

def search_uniprot_safe(protein_name):
    """Isolated UniProt search that can't break existing code"""
    try:
        query = f'gene_exact:"{protein_name}" AND organism_id:9606 AND reviewed:true'
        url = f"https://rest.uniprot.org/uniprotkb/search?query={quote_plus(query)}&format=json&fields=accession,protein_name,sequence&size=1"
        
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        
        data = response.json()
        if data['results']:
            return {
                'name': data['results'][0]['proteinName']['value'],
                'sequence': data['results'][0]['sequence']['value'],
                'source': 'UniProt'
            }
        return None
    except Exception as e:
        print(f"UniProt Error for {protein_name}: {str(e)}")
        return None

def get_amino_acid_sequences(proteins):
    """Modified isolated function that preserves original functionality"""
    results = []
    
    # Convert all protein entries to standardized names FIRST
    processed_names = [safe_protein_name(p) for p in proteins]
    print(f"Processing proteins: {processed_names}")
    
    for name in processed_names:
        try:
            # Try UniProt first
            uniprot_data = search_uniprot_safe(name)
            if uniprot_data:
                results.append(uniprot_data)
                continue
                
            # Fallback to GPT-4 with strict formatting
            response = client.chat.completions.create(
                model="gpt-4",
                messages=[
                    {"role": "system", "content": """You are a protein sequence expert. 
                    Respond ONLY with: ">Protein_Name\nSEQUENCE"""},
                    {"role": "user", "content": f"Provide {name} amino acid sequence in FASTA format"}
                ],
                temperature=0.3,
                max_tokens=500
            )
            
            fasta = response.choices[0].message.content.strip()
            results.append({
                'name': name,
                'sequence': fasta.split('\n', 1)[-1].replace(' ', ''),
                'source': 'GPT-4'
            })
        except Exception as e:
            results.append({
                'name': name,
                'sequence': f"Error: {str(e)}",
                'source': 'Failed'
            })
    
    # Build output without affecting existing UI
    output = []
    for result in results:
        output.append(f"""
        <div style="margin: 10px 0; padding: 10px; border: 1px solid #eee; border-radius: 5px;">
            <b>{result['name']}</b> ({result['source']})<br>
            <code>{result['sequence'][:50]}...</code>
            <button onclick="this.nextSibling.style.display='block'">Show Full</button>
            <div style="display: none; word-wrap: break-word;">{result['sequence']}</div>
        </div>
        """)
    
    return f"""
    <div style="margin-top: 20px;">
        <h4>Amino Acid Sequences</h4>
        {"".join(output)}
    </div>
    """


# --- Streamlit UI ---
st.title("Drug Discovery Platform - Protein Target Finder")

# Initialize session state
if 'targets' not in st.session_state:
    st.session_state.targets = []
if 'sequences' not in st.session_state:  # Add this line
    st.session_state.sequences = None

# Disease input with unique key
disease_input = st.text_input("Enter disease name (e.g., ALS):", key="disease_input")

# Protein target section
if st.button("Find Protein Targets", key="find_targets"):
    if disease_input:
        with st.spinner("Searching for protein targets..."):
            st.session_state.targets = get_protein_targets(disease_input)
            st.session_state.sequences = None  # Reset sequences when new targets are searched
            
        if st.session_state.targets:
            st.success("Found protein targets:")
            st.json(st.session_state.targets)
        else:
            st.warning("No targets found")
    else:
        st.error("Please enter a disease name")

# Amino acid sequence section
if st.session_state.targets:
    st.divider()
    st.subheader("Sequence Analysis")
    
    if st.button("Generate Amino Acid Sequences", key="generate_sequences"):
        with st.spinner("Generating sequences (may take 1-2 minutes)..."):
            st.session_state.sequences = get_amino_acid_sequences(st.session_state.targets)
        
        # Empty container to avoid layout jumps
        sequence_container = st.empty()
        
        if st.session_state.sequences:
            sequence_container.markdown(st.session_state.sequences, unsafe_allow_html=True)
        else:
            sequence_container.warning("Failed to generate sequences")
            
    # Show existing sequences if they exist
    elif st.session_state.sequences:
        st.markdown(st.session_state.sequences, unsafe_allow_html=True)
