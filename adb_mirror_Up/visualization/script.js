const canvas = document.getElementById('graph-canvas');
const ctx = canvas.getContext('2d');
const tooltip = document.getElementById('tooltip');
const depthSortBtn = document.getElementById('depth-sort-btn');

// --- Layout Constants ---
const TWEEN_FACTOR = 0.08; // For smooth layout transitions and dragging

// --- Global State ---
let nodes = [];
let edges = [];
let nodeMap = new Map(); // Map ID to index
let adj = new Map(); // Adjacency list for graph traversal

let dragging = false, dragIndex = -1;
let panning = false;
let hoverIndex = -1;
let pointer = { x: 0, y: 0 }; // World coordinates
let lastPointer = { x: 0, y: 0 }; // For panning

let view = { x: 0, y: 0, scale: 1.0 };

class Node {
    constructor(data) {
        this.id = data.id;
        this.label = data.label;
        this.type = data.type;
        this.size = data.size || 6;
        this.imagePath = data.image;
        this.image = null;
        this.is_root = data.is_root || false;

        // Final render position
        this.x = 0;
        this.y = 0;

        // Target position for layout
        this.targetX = (Math.random() - 0.5) * 1000;
        this.targetY = (Math.random() - 0.5) * 1000;
        this.depth = -1;

        if (this.imagePath) {
            this.image = new Image();
            this.image.src = this.imagePath;
        }
    }

    draw(ctx) {
        ctx.beginPath();
        if (this.is_root) {
            ctx.fillStyle = '#9c27b0'; // Purple for root
            ctx.strokeStyle = '#e1bee7';
        } else if (this.type === 'page') {
            ctx.fillStyle = '#ff5722';
            ctx.strokeStyle = '#ffccbc';
        } else {
            ctx.fillStyle = '#2196f3';
            ctx.strokeStyle = '#bbdefb';
        }
        if (hoverIndex === this.index) {
            ctx.fillStyle = '#fdd835';
        }
        ctx.lineWidth = 2;
        ctx.arc(this.x, this.y, this.size, 0, Math.PI * 2);
        ctx.fill();
        ctx.stroke();

        ctx.fillStyle = 'white';
        ctx.font = '10px sans-serif';
        ctx.textAlign = 'center';
        ctx.fillText(this.label, this.x, this.y + this.size + 10);
    }
}

function screenToWorld(sx, sy) {
    const rect = canvas.getBoundingClientRect();
    const x = (sx - rect.left - view.x) / view.scale;
    const y = (sy - rect.top - view.y) / view.scale;
    return { x, y };
}

async function init() {
    try {
        const response = await fetch('graph.json');
        const data = await response.json();

        data.nodes.forEach((d, i) => {
            const node = new Node(d);
            node.index = i;
            nodes.push(node);
            nodeMap.set(d.id, i);
            adj.set(i, []);
        });

        data.edges.forEach(d => {
            const sourceIndex = nodeMap.get(d.source);
            const targetIndex = nodeMap.get(d.target);
            if (sourceIndex !== undefined && targetIndex !== undefined) {
                edges.push({ a: sourceIndex, b: targetIndex, type: d.type });
                adj.get(sourceIndex).push(targetIndex);
            }
        });

    } catch (error) {
        console.error("Failed to load graph data:", error);
        ctx.fillStyle = 'red';
        ctx.font = '20px sans-serif';
        ctx.fillText("Failed to load graph.json", 50, 50);
        return;
    }

    setupCanvas();
    setupMouseHandlers();
    arrangeByDepth(); // Set initial layout
    requestAnimationFrame(update);
}

function setupCanvas() {
    canvas.width = window.innerWidth;
    canvas.height = window.innerHeight;
    view.x = canvas.width / 2;
    view.y = canvas.height / 2;
}

function update() {
    // Tween nodes towards their target positions
    for (const n of nodes) {
        if (dragging && n.index === dragIndex) {
            n.targetX = n.x; // While dragging, target follows the node
            n.targetY = n.y;
        } else {
            n.x += (n.targetX - n.x) * TWEEN_FACTOR;
            n.y += (n.targetY - n.y) * TWEEN_FACTOR;
        }
    }

    render();
    requestAnimationFrame(update);
}

function render() {
    ctx.clearRect(0, 0, canvas.width, canvas.height);
    ctx.save();
    ctx.translate(view.x, view.y);
    ctx.scale(view.scale, view.scale);

    ctx.lineWidth = 1.5;
    for (const e of edges) {
        const na = nodes[e.a];
        const nb = nodes[e.b];

        const dx = nb.x - na.x;
        const dy = nb.y - na.y;
        const dist = Math.hypot(dx, dy);
        if (dist < na.size + nb.size) continue;

        const angle = Math.atan2(dy, dx);
        const startX = na.x + Math.cos(angle) * na.size;
        const startY = na.y + Math.sin(angle) * na.size;
        const endX = nb.x - Math.cos(angle) * nb.size;
        const endY = nb.y - Math.sin(angle) * nb.size;

        const color = e.type === 'transition' ? 'rgba(255, 224, 130, 0.8)' : 'rgba(200, 200, 200, 0.5)';
        ctx.strokeStyle = color;

        ctx.beginPath();
        ctx.moveTo(startX, startY);
        ctx.lineTo(endX, endY);
        ctx.stroke();

        if (e.type === 'transition') {
            const arrowSize = 8;
            ctx.save();
            ctx.translate(endX, endY);
            ctx.rotate(angle);
            ctx.beginPath();
            ctx.moveTo(0, 0);
            ctx.lineTo(-arrowSize, -arrowSize / 2);
            ctx.lineTo(-arrowSize, arrowSize / 2);
            ctx.closePath();
            ctx.fillStyle = color;
            ctx.fill();
            ctx.restore();
        }
    }

    for (const n of nodes) {
        n.draw(ctx);
    }

    ctx.restore();
}

function arrangeByDepth() {
    const rootNode = nodes.find(n => n.is_root);
    if (!rootNode) {
        console.warn("Root node not found, falling back to 'page_mainPage'.");
        const mainPageNode = nodes.find(n => n.id === 'page_mainPage');
        if (!mainPageNode) return;
        rootNode = mainPageNode;
    }

    for (const n of nodes) n.depth = -1;
    const queue = [{ nodeId: rootNode.index, depth: 0 }];
    const visited = new Set([rootNode.index]);
    rootNode.depth = 0;
    let maxDepth = 0;
    let head = 0;
    while(head < queue.length) {
        const { nodeId, depth } = queue[head++];
        maxDepth = Math.max(maxDepth, depth);
        if (adj.has(nodeId)) {
            for (const neighborIdx of adj.get(nodeId)) {
                if (!visited.has(neighborIdx)) {
                    visited.add(neighborIdx);
                    nodes[neighborIdx].depth = depth + 1;
                    queue.push({ nodeId: neighborIdx, depth: depth + 1 });
                }
            }
        }
    }

    const nodesByDepth = new Map();
    for (const n of nodes) {
        if (n.depth === -1) continue;
        if (!nodesByDepth.has(n.depth)) {
            nodesByDepth.set(n.depth, []);
        }
        nodesByDepth.get(n.depth).push(n);
    }

    const COLUMN_WIDTH = 300;
    const ROW_HEIGHT = 80;
    let max_x_multiplier = 0;

    for (const [depth, nodesInColumn] of nodesByDepth.entries()) {
        const columnHeight = (nodesInColumn.length - 1) * ROW_HEIGHT;
        const yStart = -columnHeight / 2;

        nodesInColumn.forEach((node, index) => {
            const isPage = node.type === 'page';
            const x_multiplier = Math.floor(node.depth / 2) + (isPage ? 0 : 0.5);
            
            node.targetX = x_multiplier * COLUMN_WIDTH;
            node.targetY = yStart + index * ROW_HEIGHT;

            if (x_multiplier > max_x_multiplier) {
                max_x_multiplier = x_multiplier;
            }
        });
    }
    
    const totalWidth = max_x_multiplier * COLUMN_WIDTH;
    for (const n of nodes) {
        if (n.depth !== -1) {
            n.targetX -= totalWidth / 2;
        } else {
            n.targetX = (max_x_multiplier / 2) + COLUMN_WIDTH;
            n.targetY = 0;
        }
    }
}

function setupMouseHandlers() {
    depthSortBtn.addEventListener('click', arrangeByDepth);

    canvas.addEventListener('wheel', e => {
        e.preventDefault();
        const pointerBeforeZoom = screenToWorld(e.clientX, e.clientY);
        
        const zoomFactor = 1.1;
        const newScale = e.deltaY < 0 ? view.scale * zoomFactor : view.scale / zoomFactor;
        view.scale = Math.max(0.1, Math.min(5, newScale));

        const pointerAfterZoom = screenToWorld(e.clientX, e.clientY);

        view.x += (pointerAfterZoom.x - pointerBeforeZoom.x) * view.scale;
        view.y += (pointerAfterZoom.y - pointerBeforeZoom.y) * view.scale;
    });

    canvas.addEventListener('mousedown', e => {
        const worldPos = screenToWorld(e.clientX, e.clientY);
        lastPointer = { x: e.clientX, y: e.clientY };

        let foundIndex = -1;
        for (let i = nodes.length - 1; i >= 0; i--) {
            const n = nodes[i];
            const dist = Math.hypot(worldPos.x - n.x, worldPos.y - n.y);
            if (dist < n.size) {
                foundIndex = i;
                break;
            }
        }

        if (foundIndex !== -1) {
            dragging = true;
            dragIndex = foundIndex;
        } else {
            panning = true;
        }
    });

    canvas.addEventListener('mousemove', e => {
        const worldPos = screenToWorld(e.clientX, e.clientY);
        if (dragging) {
            const n = nodes[dragIndex];
            n.x = worldPos.x;
            n.y = worldPos.y;
        } else if (panning) {
            view.x += e.clientX - lastPointer.x;
            view.y += e.clientY - lastPointer.y;
            lastPointer = { x: e.clientX, y: e.clientY };
        } else {
            let foundIndex = -1;
            for (let i = nodes.length - 1; i >= 0; i--) {
                const n = nodes[i];
                const dist = Math.hypot(worldPos.x - n.x, worldPos.y - n.y);
                if (dist < n.size) {
                    foundIndex = i;
                    break;
                }
            }
            hoverIndex = foundIndex;
        }

        if (hoverIndex !== -1) {
            const n = nodes[hoverIndex];
            tooltip.style.display = 'block';
            tooltip.style.left = `${e.clientX + 15}px`;
            tooltip.style.top = `${e.clientY}px`;
            let content = `<b>${n.label}</b><br>Type: ${n.type}<br>Depth: ${n.depth}`;
            if (n.image && n.image.complete) {
                content += `<img src="${n.image.src}">`;
            }
            tooltip.innerHTML = content;
        } else {
            tooltip.style.display = 'none';
        }
    });

    canvas.addEventListener('mouseup', e => {
        dragging = false;
        dragIndex = -1;
        panning = false;
    });
    
    canvas.addEventListener('mouseout', () => {
        panning = false;
    });

    window.addEventListener('resize', setupCanvas);
}

init();
