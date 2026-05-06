let speciesData = [];
let currentTree = null;
let currentImgIdx = 0;
let isZoomed = false;

const grid = document.getElementById('card-grid');
const searchInput = document.getElementById('search-input');
const modal = document.getElementById('modal');
const mainImage = document.getElementById('main-image');
const wrapper = document.getElementById('image-wrapper');
const modalName = document.getElementById('modal-name');
const modalDesc = document.getElementById('modal-desc');

async function init() {
    const res = await fetch('botanical_index.json');
    const data = await res.json();
    speciesData = data.species;
    renderGrid(speciesData);
}

function renderGrid(data) {
    grid.innerHTML = '';
    data.forEach((tree, idx) => {
        const card = document.createElement('div');
        card.className = 'card';
        card.innerHTML = `
            <img src="${tree.images[0]}" class="card-img" loading="lazy">
            <div class="card-content">
                <div class="card-category">한국의 나무</div>
                <div class="card-title">${tree.name}</div>
            </div>
        `;
        card.onclick = () => openModal(tree);
        grid.appendChild(card);
    });
}

function openModal(tree) {
    currentTree = tree;
    currentImgIdx = 0;
    isZoomed = false;
    
    modalName.textContent = tree.name;
    modalDesc.textContent = tree.details || tree.summary;
    updateImage();
    
    modal.classList.add('active');
    document.body.style.overflow = 'hidden';
}

function updateImage() {
    mainImage.src = currentTree.images[currentImgIdx];
    resetZoom();
}

function resetZoom() {
    isZoomed = false;
    wrapper.classList.remove('zoomed');
    mainImage.style.transform = 'translate(0, 0) scale(1)';
}

// Carousel Logic
document.getElementById('prev-btn').onclick = (e) => {
    e.stopPropagation();
    currentImgIdx = (currentImgIdx - 1 + currentTree.images.length) % currentTree.images.length;
    updateImage();
};

document.getElementById('next-btn').onclick = (e) => {
    e.stopPropagation();
    currentImgIdx = (currentImgIdx + 1) % currentTree.images.length;
    updateImage();
};

// Zoom & Pan Logic (Exactly like reference)
wrapper.onclick = () => {
    isZoomed = !isZoomed;
    wrapper.classList.toggle('zoomed', isZoomed);
    if (!isZoomed) {
        mainImage.style.transform = 'translate(0, 0) scale(1)';
    } else {
        mainImage.style.transform = 'scale(2.5)';
    }
};

wrapper.onmousemove = (e) => {
    if (!isZoomed) return;
    
    const { left, top, width, height } = wrapper.getBoundingClientRect();
    const x = (e.clientX - left) / width;
    const y = (e.clientY - top) / height;
    
    // Smooth panning effect
    const panX = (0.5 - x) * 100;
    const panY = (0.5 - y) * 100;
    
    mainImage.style.transform = `translate(${panX}%, ${panY}%) scale(2.5)`;
};

// Close Logic
document.getElementById('close-modal').onclick = () => {
    modal.classList.remove('active');
    document.body.style.overflow = 'auto';
};

window.onclick = (e) => {
    if (e.target === modal) {
        modal.classList.remove('active');
        document.body.style.overflow = 'auto';
    }
};

// Search Logic
searchInput.oninput = (e) => {
    const term = e.target.value.toLowerCase();
    const filtered = speciesData.filter(t => t.name.includes(term));
    renderGrid(filtered);
};

init();
