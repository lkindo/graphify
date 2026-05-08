import json
import re

def merge_and_update():
    # Load data
    with open("botanical_index.json", "r", encoding="utf-8") as f:
        botanical_data = json.load(f)
    
    with open("flower_index.json", "r", encoding="utf-8") as f:
        flower_data = json.load(f)
    
    # Combine species
    all_species = botanical_data["species"] + flower_data["species"]
    
    # Sort by name
    all_species.sort(key=lambda x: x["name"])
    
    # Read index.html
    with open("index.html", "r", encoding="utf-8") as f:
        html = f.read()
    
    # Prepare JSON string
    json_str = json.dumps(all_species, ensure_ascii=False, indent=4)
    
    # 1. Replace speciesData declaration
    script_pattern = "let speciesData = [];"
    html = html.replace(script_pattern, f"const speciesData = {json_str};")
    
    # 2. Update init() to not fetch
    # We find the start and end of the init function
    start_marker = "async function init() {"
    end_marker = "        }"
    
    start_idx = html.find(start_marker)
    # Find the closing brace of the catch block
    catch_idx = html.find("catch (e) {", start_idx)
    inner_close_idx = html.find("}", catch_idx)
    final_close_idx = html.find("}", inner_close_idx + 1)
    
    if start_idx != -1 and final_close_idx != -1:
        new_init = """function init() {
            renderGrid(speciesData);
        }"""
        html = html[:start_idx] + new_init + html[final_close_idx+1:]
    
    # 3. Add '나무에 피는 꽃' search button
    search_container_old = '<div class="search-container">'
    search_container_new = '<div class="search-container" style="display: flex; gap: 10px; width: 500px;">'
    html = html.replace(search_container_old, search_container_new)
    
    input_pattern = '<input type="text" id="search-input" placeholder="나무 이름을 입력하세요...">'
    input_replacement = '<input type="text" id="search-input" placeholder="나무 이름을 입력하세요...">\n            <button id="flower-btn" style="white-space: nowrap; background: var(--accent); border: none; border-radius: 12px; padding: 0 1.2rem; color: white; font-weight: 700; cursor: pointer; transition: 0.3s; height: 45px;">나무에 피는 꽃</button>'
    html = html.replace(input_pattern, input_replacement)
    
    # 4. Add button logic
    button_logic = """
        document.getElementById('flower-btn').onclick = () => {
            searchInput.value = '나무에 피는 꽃';
            const filtered = speciesData.filter(t => 
                t.name.toLowerCase().includes('나무에 피는 꽃') || 
                t.category.toLowerCase().includes('나무에 피는 꽃')
            );
            renderGrid(filtered);
        };
    """
    html = html.replace("init();", button_logic + "\n        init();")
    
    # Save index.html
    with open("index.html", "w", encoding="utf-8") as f:
        f.write(html)
    
    print("Merge and Update Complete!")

if __name__ == "__main__":
    merge_and_update()
