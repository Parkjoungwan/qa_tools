const canvas = document.getElementById('graph-canvas');
const ctx = canvas.getContext('2d');
const tooltip = document.getElementById('tooltip');
const depthSortBtn = document.getElementById('depth-sort-btn');
const makeRouteBtn = document.getElementById('make-route-btn');
const extractRouteBtn = document.getElementById('extract-route-btn');

// --- Layout Constants ---
const TWEEN_FACTOR = 0.08;

// --- Global State ---
let nodes = [];
let edges = [];
let nodeMap = new Map();
let adj = new Map();

let dragging = false, dragIndex = -1;
let panning = false;
let hoverIndex = -1;
let pointer = { x: 0, y: 0 };
let lastPointer = { x: 0, y: 0 };

let view = { x: 0, y: 0, scale: 1.0 };

// Route creation state
let routeCreationActive = false;
let selectedRoute = []; // Array of node indices
let paginationInfo = null; // To store pagination button coordinates

class Node {
    constructor(data) {
        this.id = data.id;
        this.label = data.label;
        this.type = data.type;
        this.size = data.size || 6;
        this.imagePath = data.image;
        this.logLine = data.logLine; // Store the original log line
        this.is_root = data.is_root || false;
        this.image = null;

        this.x = 0;
        this.y = 0;
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
        ctx.fillText(this.label, this.x, this.y + this.size + 12);

        // Draw route order number
        const routeIndex = selectedRoute.indexOf(this.index);
        if (routeIndex > -1) {
            ctx.fillStyle = 'white';
            ctx.font = 'bold 12px sans-serif';
            ctx.textAlign = 'center';
            ctx.textBaseline = 'middle';
            ctx.fillText(routeIndex + 1, this.x, this.y);
        }
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
        // Fetch graph data and pagination info in parallel
        const [graphResponse, paginationResponse] = await Promise.all([
            fetch('graph.json'),
            fetch('../page_fingerprints/pagination_mainPage/pagination_info.json').catch(e => null)
        ]);

        const data = await graphResponse.json();
        if (paginationResponse && paginationResponse.ok) {
            paginationInfo = await paginationResponse.json();
            console.log("Pagination info loaded.");
        }

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
    arrangeByDepth();
    requestAnimationFrame(update);
}

function setupCanvas() {
    canvas.width = window.innerWidth;
    canvas.height = window.innerHeight;
    view.x = canvas.width / 2;
    view.y = canvas.height / 2;
}

function update() {
    for (const n of nodes) {
        if (dragging && n.index === dragIndex) {
            n.targetX = n.x;
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
        if (!na || !nb) continue;

        const dx = nb.x - na.x;
        const dy = nb.y - na.y;
        const dist = Math.hypot(dx, dy);
        if (dist < na.size + nb.size) continue;

        const angle = Math.atan2(dy, dx);
        const startX = na.x + Math.cos(angle) * na.size;
        const startY = na.y + Math.sin(angle) * na.size;
        const endX = nb.x - Math.cos(angle) * nb.size;
        const endY = nb.y - Math.sin(angle) * nb.size;

        const color = e.type === 'transition' || e.type === 'pagination' ? 'rgba(255, 224, 130, 0.8)' : 'rgba(200, 200, 200, 0.5)';
        ctx.strokeStyle = color;

        ctx.beginPath();
        ctx.moveTo(startX, startY);
        ctx.lineTo(endX, endY);
        ctx.stroke();

        if (e.type === 'transition' || e.type === 'pagination') {
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
    const rootNode = nodes.find(n => n.id === 'page_mainPage_1');
    if (!rootNode) {
        console.error("Root node 'page_mainPage_1' not found!");
        return;
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
                    const neighborNode = nodes[neighborIdx];
                    if (nodes[nodeId].id.startsWith('page_mainPage') && neighborNode.id.startsWith('page_mainPage')) {
                        neighborNode.depth = depth; // Keep same depth for mainPage transitions
                        queue.unshift({ nodeId: neighborIdx, depth: depth }); // Prioritize mainPage siblings
                    } else {
                        neighborNode.depth = depth + 1;
                        queue.push({ nodeId: neighborIdx, depth: depth + 1 });
                    }
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

function findShortestPath(startNodeIdx, endNodeIdx) {
    const queue = [[startNodeIdx]];
    const visited = new Set([startNodeIdx]);

    while (queue.length > 0) {
        const path = queue.shift();
        const lastNodeIdx = path[path.length - 1];

        if (lastNodeIdx === endNodeIdx) {
            return path;
        }

        // Add graph-based neighbors
        if (adj.has(lastNodeIdx)) {
            for (const neighborIdx of adj.get(lastNodeIdx)) {
                if (!visited.has(neighborIdx)) {
                    visited.add(neighborIdx);
                    const newPath = [...path, neighborIdx];
                    queue.push(newPath);
                }
            }
        }

        // Add implicit pagination neighbors for mainPage nodes
        const lastNode = nodes[lastNodeIdx];
        if (lastNode.id.startsWith('page_mainPage')) {
            for (const node of nodes) {
                if (node.id.startsWith('page_mainPage') && !visited.has(node.index)) {
                    visited.add(node.index);
                    const newPath = [...path, node.index];
                    queue.push(newPath);
                }
            }
        }
    }
    return null; // No path found
}

function extractRoute() {
    if (selectedRoute.length < 2) {
        alert("Please select at least two pages to create a route.");
        return;
    }

    // Find a fallback serial from any tap node in the graph
    let fallbackSerial = '';
    const anyTapNode = nodes.find(n => n.type === 'tap' && n.logLine);
    if (anyTapNode) {
        const parts = anyTapNode.logLine.split('\t');
        if (parts.length > 2) {
            fallbackSerial = parts[2];
        }
    }

    let fullPath = [];
    for (let i = 0; i < selectedRoute.length - 1; i++) {
        const startNodeIdx = selectedRoute[i];
        const endNodeIdx = selectedRoute[i+1];
        
        const pathSegment = findShortestPath(startNodeIdx, endNodeIdx);
        if (!pathSegment) {
            const startNode = nodes[startNodeIdx];
            const endNode = nodes[endNodeIdx];
            alert(`No path found from ${startNode.label} to ${endNode.label}`);
            return;
        }
        fullPath.push(...(i === 0 ? pathSegment : pathSegment.slice(1)));
    }

    const tapLogs = [];
    let currentElapsed = 0.00;
    const ELAPSED_INCREMENT = 1.50;
    let lastSerial = ''

    for (let i = 0; i < fullPath.length; i++) {
        const node = nodes[fullPath[i]];

        if (node.type === 'tap' && node.logLine) {
            const parts = node.logLine.split('\t');
            const type = parts[0] || '';
            lastSerial = parts[2] || '';
            const text = parts[4] || '';
            const x1 = parts[5] || '';
            const y1 = parts[6] || '';
            const x2 = parts[7] || '';
            const y2 = parts[8] || '';
            const duration = parts[9] || '';

            tapLogs.push(
                `${type}\t${currentElapsed.toFixed(2)}\t${lastSerial}\t${text}\t${x1}\t${y1}\t${x2}\t${y2}\t${duration}`
            );
            currentElapsed += ELAPSED_INCREMENT;
        }

        // Check for mainPage pagination
        if (i + 1 < fullPath.length) {
            const nextNode = nodes[fullPath[i+1]];
            if (node.id.startsWith('page_mainPage') && nextNode.id.startsWith('page_mainPage') && node.id !== nextNode.id) {
                if (!paginationInfo) {
                    alert("Pagination info is not loaded. Cannot generate pagination taps.");
                    return;
                }
                const currentPageNum = parseInt(node.id.split('_')[2]);
                const targetPageNum = parseInt(nextNode.id.split('_')[2]);
                const diff = targetPageNum - currentPageNum;
                
                const button_key = diff > 0 ? 'right_button' : 'left_button';
                const button_coords = paginationInfo[button_key];

                const serialToUse = lastSerial || fallbackSerial || 'UNKNOWN_SERIAL';

                for (let j = 0; j < Math.abs(diff); j++) {
                    const logLine = `tap\t${currentElapsed.toFixed(2)}\t${serialToUse}\t\t${button_coords.x}\t${button_coords.y}`;
                    tapLogs.push(logLine);
                    currentElapsed += ELAPSED_INCREMENT;
                }
            }
        }
    }

    const header = "type\telapsed\tserial\ttext\tx1\ty1\tx2\y2\tduration";
    const logContent = [header, ...tapLogs].join('\n');

    if (tapLogs.length === 0) {
        alert("No actions (taps or pagination) found for the selected route.");
        return;
    }

    const blob = new Blob([logContent], { type: 'text/plain' });
    const a = document.createElement('a');
    a.href = URL.createObjectURL(blob);
    a.download = 'route.log';
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
}

function setupMouseHandlers() {
    depthSortBtn.addEventListener('click', arrangeByDepth);
    makeRouteBtn.addEventListener('click', () => {
        routeCreationActive = !routeCreationActive;
        makeRouteBtn.classList.toggle('active', routeCreationActive);
        if (routeCreationActive) {
            selectedRoute = [];
            console.log("Route creation activated. Click page nodes to build a route.");
        } else {
            console.log("Route creation deactivated.");
        }
    });
    extractRouteBtn.addEventListener('click', extractRoute);

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
            const node = nodes[foundIndex];
            if (routeCreationActive && node.type === 'page') {
                const routePos = selectedRoute.indexOf(foundIndex);
                if (routePos > -1) {
                    selectedRoute.splice(routePos, 1);
                } else {
                    selectedRoute.push(foundIndex);
                }
            } else {
                dragging = true;
                dragIndex = foundIndex;
            }
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