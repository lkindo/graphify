import json
import os

def actualize_index():
    # 1. Load verified species list
    species_list = []
    with open("flower_index.json", "r", encoding="utf-8") as f:
        data = json.load(f)
        species_list = data["species"]

    # 2. Prepare the clean index.html template
    html_template = """<!DOCTYPE html>
<html lang="ko">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>도감</title>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;700;800&display=swap" rel="stylesheet">
    <style>
        :root {
            --bg-color: #0b0f19;
            --card-bg: #1e293b;
            --accent: #10b981;
            --text-main: #f1f5f9;
            --text-muted: #94a3b8;
            --modal-bg: rgba(10, 15, 25, 0.98);
            --glass-border: rgba(255, 255, 255, 0.1);
        }

        * { box-sizing: border-box; margin: 0; padding: 0; }

        body {
            background-color: var(--bg-color);
            color: var(--text-main);
            font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            line-height: 1.6;
            overflow-x: hidden;
        }

        header {
            background: rgba(11, 15, 25, 0.8);
            backdrop-filter: blur(20px);
            border-bottom: 1px solid var(--glass-border);
            padding: 1.2rem 5%;
            position: sticky;
            top: 0; z-index: 100;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }

        .logo {
            font-size: 1.8rem;
            font-weight: 800;
            background: linear-gradient(135deg, #10b981, #3b82f6);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            cursor: pointer;
        }

        .controls { display: flex; gap: 1rem; align-items: center; }

        .search-container { width: 300px; position: relative; }
        .search-container input {
            width: 100%;
            background: rgba(255, 255, 255, 0.05);
            border: 1px solid var(--glass-border);
            border-radius: 12px;
            padding: 0.8rem 1.2rem;
            color: white;
            font-size: 0.95rem;
            transition: all 0.3s;
        }
        .search-container input:focus {
            outline: none;
            border-color: var(--accent);
            box-shadow: 0 0 20px rgba(16, 185, 129, 0.2);
        }

        .btn {
            background: var(--accent);
            color: #fff;
            border: none;
            padding: 0.8rem 1.5rem;
            border-radius: 12px;
            font-weight: 700;
            cursor: pointer;
            transition: all 0.3s;
            box-shadow: 0 4px 15px rgba(16, 185, 129, 0.3);
        }
        .btn:hover { transform: translateY(-2px); box-shadow: 0 6px 20px rgba(16, 185, 129, 0.4); opacity: 0.9; }

        .container {
            max-width: 1600px;
            margin: 3rem auto;
            padding: 0 5%;
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(260px, 1fr));
            gap: 2.5rem;
        }

        .card {
            background: var(--card-bg);
            border-radius: 24px;
            overflow: hidden;
            cursor: pointer;
            transition: all 0.4s cubic-bezier(0.175, 0.885, 0.32, 1.275);
            border: 1px solid var(--glass-border);
            position: relative;
        }
        .card:hover { transform: translateY(-15px); border-color: var(--accent); box-shadow: 0 20px 40px rgba(0,0,0,0.4); }
        .card-img-wrapper { width: 100%; aspect-ratio: 1/1.2; overflow: hidden; background: #000; }
        .card-img { width: 100%; height: 100%; object-fit: cover; transition: transform 0.6s; }
        .card:hover .card-img { transform: scale(1.05); }
        .card-content { padding: 1.5rem; }
        .card-title { font-size: 1.3rem; font-weight: 700; margin-bottom: 0.5rem; color: #fff; }
        .card-category { font-size: 0.8rem; color: var(--accent); text-transform: uppercase; letter-spacing: 1px; font-weight: 700; }

        /* Modal Styles */
        .modal {
            position: fixed;
            top: 0; left: 0;
            width: 100%; height: 100%;
            background: var(--modal-bg);
            backdrop-filter: blur(10px);
            z-index: 2000;
            display: none;
            opacity: 0;
            transition: opacity 0.4s ease;
            align-items: center;
            justify-content: center;
        }
        .modal.active { display: flex; opacity: 1; }
        .modal-content {
            width: 90%;
            max-width: 1200px;
            height: 90vh;
            background: #111827;
            border-radius: 30px;
            border: 1px solid var(--glass-border);
            display: flex;
            overflow: hidden;
            position: relative;
        }
        .modal-close {
            position: absolute;
            top: 2rem; right: 2rem;
            background: rgba(255,255,255,0.1);
            color: #fff;
            border: none;
            width: 40px; height: 40px;
            border-radius: 50%;
            cursor: pointer;
            z-index: 1000;
            font-size: 1.2rem;
            display: flex; align-items: center; justify-content: center;
        }

        .modal-image-section { width: 100%; height: 100%; background: #000; display: flex; align-items: center; justify-content: center; position: relative; }
        .modal-main-img { max-width: 100%; max-height: 100%; object-fit: contain; cursor: zoom-in; }
        .modal-info-section { flex: 0.8; padding: 4rem 3rem; overflow-y: auto; display: flex; flex-direction: column; gap: 2rem; }
        
        .modal-title { font-size: 2.5rem; font-weight: 800; line-height: 1.2; }
        .modal-category { color: var(--accent); font-weight: 700; font-size: 1.1rem; }
        .modal-desc { color: var(--text-muted); font-size: 1.1rem; line-height: 1.8; }

        .zoom-overlay {
            position: absolute;
            top: 0; left: 0;
            width: 100%; height: 100%;
            background: #000;
            display: none;
            z-index: 100;
            cursor: zoom-out;
            overflow: auto;
        }
        .zoom-overlay.active { display: block; }
        .zoomed-image { width: 250%; transform-origin: top left; transition: transform 0.1s; }

        @media (max-width: 1000px) {
            .modal-content { height: 95vh; }
            .modal-image-section { height: 100%; }
        }
    </style>
</head>
<body>
    <header>
        <div></div>
        <div class="controls">
            <button class="btn" id="flower-btn">나무에 피는 꽃</button>
            <div class="search-container">
                <input type="text" id="search" placeholder="나무 이름을 검색하세요...">
            </div>
        </div>
    </header>

    <div class="container" id="grid"></div>

    <div class="modal" id="modal">
        <div class="modal-content">
            <button class="modal-close" id="close-modal">×</button>
            <div class="modal-image-section" id="img-wrapper">
                <img src="" alt="" class="modal-main-img" id="modal-img">
                <div class="zoom-overlay" id="zoom-overlay">
                    <img src="" alt="" class="zoomed-image" id="zoomed-img">
                </div>
            </div>
        </div>
    </div>

    <script>
        const speciesData = REPLACE_DATA;

        const grid = document.getElementById('grid');
        const modal = document.getElementById('modal');
        const searchInput = document.getElementById('search');

        function renderGrid(data) {
            grid.innerHTML = data.map(item => `
                <div class="card" onclick='openModal(${JSON.stringify(item).replace(/'/g, "&apos;")})'>
                    <div class="card-img-wrapper">
                        <img src="${item.images[0]}" class="card-img" loading="lazy">
                    </div>
                    <div class="card-content">
                        <div class="card-title">${item.name}</div>
                    </div>
                </div>
            `).join('');
        }

        function openModal(item) {
            document.getElementById('modal-img').src = item.images[0];
            document.getElementById('zoomed-img').src = item.images[0];
            
            modal.classList.add('active');
            document.body.style.overflow = 'hidden';
        }

        document.getElementById('close-modal').onclick = () => {
            modal.classList.remove('active');
            document.body.style.overflow = 'auto';
        };

        // Zoom logic
        const imgWrapper = document.getElementById('img-wrapper');
        const zoomOverlay = document.getElementById('zoom-overlay');
        const zoomedImg = document.getElementById('zoomed-img');

        imgWrapper.onclick = () => {
            zoomOverlay.classList.add('active');
        };

        zoomOverlay.onclick = () => {
            zoomOverlay.classList.remove('active');
        };

        zoomOverlay.onmousemove = (e) => {
            const { width, height } = zoomOverlay.getBoundingClientRect();
            const x = e.clientX / width;
            const y = e.clientY / height;
            zoomedImg.style.transform = `translate(${-x * 50}%, ${-y * 50}%)`;
        };

        searchInput.oninput = (e) => {
            const term = e.target.value.trim().toLowerCase();
            const filtered = speciesData.filter(t => t.name.toLowerCase().includes(term));
            renderGrid(filtered);
        };

        document.getElementById('flower-btn').onclick = () => {
            const term = '나무에 피는 꽃';
            const filtered = speciesData.filter(t => t.category.includes(term));
            renderGrid(filtered);
        };

        // Initialize
        renderGrid(speciesData);
    </script>
</body>
</html>"""

    # 3. Replace data and write
    final_html = html_template.replace("REPLACE_DATA", json.dumps(species_list, ensure_ascii=False))
    
    with open("index.html", "w", encoding="utf-8") as f:
        f.write(final_html)
    
    print("Index Page Actualized Successfully!")

if __name__ == "__main__":
    actualize_index()
