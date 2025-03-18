from flask import Flask, request, render_template_string, jsonify
from PIL import Image, ImageChops, ImageStat, UnidentifiedImageError
import io
import base64
import numpy as np

app = Flask(__name__)

@app.route("/", methods=["GET"])
def index():
    return render_template_string("""
<!DOCTYPE html>
<html>
<head>
    <title>Syst(em) Tampering Detection</title>
    <style>
        body { font-family: Arial, sans-serif; margin: 20px; background-color: #f5f5f5; }
        * { -webkit-tap-highlight-color: transparent; -webkit-font-smoothing: antialiased; text-rendering: optimizeLegibility; scroll-behavior: smooth; scrollbar-width: thin; scrollbar-color: #4f4e4e #232323;}
        .container { display: flex; flex-direction: column; gap: 20px; }
        .workspace { display: flex; gap: 20px; flex-wrap: wrap; }
        .controls { margin-bottom: 20px; }
        button { padding: 8px 12px; margin-right: 10px; }
        .result { margin-top: 20px; padding: 15px; }
        .slider-container label { display: inline-block; width: 120px; }
        .slider-container input[type="range"] { width: 200px; }
        .slider-container input[type="number"] { width: 60px; }
    </style>
</head>
<body>
    <h2>Syst(em) Anti-Tampering Pattern Verification</h2>
    
    <div class="container">
        <div class="upload-section">
            <h3>Upload :</h3>
            <div>
                <label>Control Image: </label>
                <input type="file" id="controlImage" accept="image/*">
            </div>
            <div>
                <label>Test Image : </label>
                <input type="file" id="testImage" accept="image/*">
            </div>
        </div>
        
        <div class="overlay-controls" id="overlayControls" style="display: none;">
            <h3>Test Controls :</h3>
            <div class="slider-container">
                <label for="scaleSlider">Scale: </label>
                <input type="range" id="scaleSlider" min="0.1" max="2" step="0.05" value="1">
                <input type="number" id="scaleValue" min="0.1" max="2" step="0.05" value="1" style="margin-left: 10px;">
            </div>
            <div class="slider-container">
                <label for="opacitySlider">Opacity: </label>
                <input type="range" id="opacitySlider" min="0.1" max="1" step="0.05" value="0.7">
                <input type="number" id="opacityValue" min="0.1" max="1" step="0.05" value="0.7" style="margin-left: 10px;">
            </div>
        </div>
        
        <div class="controls">
            <button id="positionBtn" disabled>Position Test Image</button>
            <button id="selectRegionBtn" disabled>Select Region To Compare</button>
            <button id="compareBtn" disabled>Compare</button>
            <button id="resetBtn">Reset</button>
        </div>
        
        <div class="workspace">
            <div>
                <h3>Workspace :</h3>
                <div class="image-container">
                    <canvas id="canvas" width="800" height="600"></canvas>
                </div>
            </div>
        </div>
        
        <div class="result" id="result">
        </div>
    </div>

    <script>
        // Global variables
        let baseImg = null;
        let overlayImg = null;
        let canvas = document.getElementById('canvas');
        let ctx = canvas.getContext('2d');
        let dragMode = false;
        let offsetX = 0, offsetY = 0;
        let startX, startY;
        let selectionMode = false;
        let selection = { x: 0, y: 0, width: 0, height: 0 };
        let hasSelection = false;
        let scale = 1.0;
        let opacity = 0.7;
        
        // Load images
        document.getElementById('controlImage').addEventListener('change', function(e) {
            const file = e.target.files[0];
            const reader = new FileReader();
            reader.onload = function(event) {
                baseImg = new Image();
                baseImg.onload = function() {
                    resetWorkspace();
                    document.getElementById('selectRegionBtn').disabled = false;
                    redrawCanvas();
                };
                baseImg.src = event.target.result;
            };
            reader.readAsDataURL(file);
        });
        
        document.getElementById('testImage').addEventListener('change', function(e) {
            const file = e.target.files[0];
            const reader = new FileReader();
            reader.onload = function(event) {
                overlayImg = new Image();
                overlayImg.onload = function() {
                    document.getElementById('positionBtn').disabled = false;
                    document.getElementById('overlayControls').style.display = 'block';
                    redrawCanvas();
                };
                overlayImg.src = event.target.result;
            };
            reader.readAsDataURL(file);
        });
        
        // Scale and opacity controls
        document.getElementById('scaleSlider').addEventListener('input', function(e) {
            scale = parseFloat(e.target.value);
            document.getElementById('scaleValue').value = scale;
            redrawCanvas();
        });
        
        document.getElementById('scaleValue').addEventListener('change', function(e) {
            scale = parseFloat(e.target.value);
            document.getElementById('scaleSlider').value = scale;
            redrawCanvas();
        });
        
        document.getElementById('opacitySlider').addEventListener('input', function(e) {
            opacity = parseFloat(e.target.value);
            document.getElementById('opacityValue').value = opacity;
            redrawCanvas();
        });
        
        document.getElementById('opacityValue').addEventListener('change', function(e) {
            opacity = parseFloat(e.target.value);
            document.getElementById('opacitySlider').value = opacity;
            redrawCanvas();
        });
        
        // Button controls
        document.getElementById('positionBtn').addEventListener('click', function() {
            if (!baseImg || !overlayImg) return;
            dragMode = true;
            selectionMode = false;
            canvas.style.cursor = 'move';
        });
        
        document.getElementById('selectRegionBtn').addEventListener('click', function() {
            if (!baseImg) return;
            dragMode = false;
            selectionMode = true;
            canvas.style.cursor = 'crosshair';
        });
        
        document.getElementById('compareBtn').addEventListener('click', function() {
            if (!hasSelection) return;
            compareRegions();
        });
        
        document.getElementById('resetBtn').addEventListener('click', function() {
            resetWorkspace();
        });
        
        function resetWorkspace() {
            offsetX = 0;
            offsetY = 0;
            scale = 1.0;
            opacity = 0.7;
            selection = { x: 0, y: 0, width: 0, height: 0 };
            hasSelection = false;
            dragMode = false;
            selectionMode = false;
            document.getElementById('compareBtn').disabled = true;
            document.getElementById('scaleSlider').value = scale;
            document.getElementById('scaleValue').value = scale;
            document.getElementById('opacitySlider').value = opacity;
            document.getElementById('opacityValue').value = opacity;
            redrawCanvas();
        }
        
        // Canvas mouse events
        canvas.addEventListener('mousedown', function(e) {
            const rect = canvas.getBoundingClientRect();
            startX = e.clientX - rect.left;
            startY = e.clientY - rect.top;
            
            if (selectionMode) {
                selection.x = startX;
                selection.y = startY;
                selection.width = 0;
                selection.height = 0;
            }
        });
        
        canvas.addEventListener('mousemove', function(e) {
            if (!e.buttons) return;
            
            const rect = canvas.getBoundingClientRect();
            const x = e.clientX - rect.left;
            const y = e.clientY - rect.top;
            
            if (dragMode && overlayImg) {
                offsetX += (x - startX);
                offsetY += (y - startY);
                startX = x;
                startY = y;
                redrawCanvas();
            } else if (selectionMode) {
                selection.width = x - selection.x;
                selection.height = y - selection.y;
                redrawCanvas();
            }
        });
        
        canvas.addEventListener('mouseup', function() {
            if (selectionMode && selection.width && selection.height) {
                // Ensure positive width and height
                if (selection.width < 0) {
                    selection.x += selection.width;
                    selection.width = Math.abs(selection.width);
                }
                if (selection.height < 0) {
                    selection.y += selection.height;
                    selection.height = Math.abs(selection.height);
                }
                
                hasSelection = true;
                document.getElementById('compareBtn').disabled = false;
                redrawCanvas();
            }
        });
        
        function redrawCanvas() {
            ctx.clearRect(0, 0, canvas.width, canvas.height);
            
            if (baseImg) {
                ctx.drawImage(baseImg, 0, 0, baseImg.width, baseImg.height, 
                              0, 0, canvas.width, canvas.height);
            }
            
            if (overlayImg) {
                // Calculate scaled dimensions
                const scaledWidth = canvas.width * scale;
                const scaledHeight = canvas.height * scale;
                
                // Calculate center offset to keep overlay centered during scaling
                const centerOffsetX = (canvas.width - scaledWidth) / 2;
                const centerOffsetY = (canvas.height - scaledHeight) / 2;
                
                // Draw with semi-transparency and scaling
                ctx.globalAlpha = opacity;
                ctx.drawImage(overlayImg, 0, 0, overlayImg.width, overlayImg.height, 
                              offsetX + centerOffsetX, offsetY + centerOffsetY, 
                              scaledWidth, scaledHeight);
                ctx.globalAlpha = 1.0;
            }
            
            // Draw selection rectangle
            if (hasSelection || (selectionMode && selection.width && selection.height)) {
                ctx.strokeStyle = 'red';
                ctx.lineWidth = 2;
                ctx.strokeRect(selection.x, selection.y, selection.width, selection.height);
            }
        }
        
        function compareRegions() {
            if (!baseImg || !overlayImg || !hasSelection) return;
            
            // Create canvas elements for the selected regions
            const baseCanvas = document.createElement('canvas');
            const overlayCanvas = document.createElement('canvas');
            baseCanvas.width = selection.width;
            baseCanvas.height = selection.height;
            overlayCanvas.width = selection.width;
            overlayCanvas.height = selection.height;
            
            // Draw selected regions from base image
            const baseCtx = baseCanvas.getContext('2d');
            baseCtx.drawImage(baseImg, 
                              selection.x * (baseImg.width / canvas.width), 
                              selection.y * (baseImg.height / canvas.height),
                              selection.width * (baseImg.width / canvas.width),
                              selection.height * (baseImg.height / canvas.height),
                              0, 0, selection.width, selection.height);
            
            // Calculate scaled dimensions and offsets for overlay
            const scaledWidth = canvas.width * scale;
            const scaledHeight = canvas.height * scale;
            const centerOffsetX = (canvas.width - scaledWidth) / 2;
            const centerOffsetY = (canvas.height - scaledHeight) / 2;
            
            // Calculate the position in the original overlay image
            const overlayCtx = overlayCanvas.getContext('2d');
            const selectionInOverlayX = (selection.x - offsetX - centerOffsetX) / scale;
            const selectionInOverlayY = (selection.y - offsetY - centerOffsetY) / scale;
            const selectionInOverlayWidth = selection.width / scale;
            const selectionInOverlayHeight = selection.height / scale;
            
            // Draw from the overlay image
            overlayCtx.drawImage(overlayImg,
                                selectionInOverlayX * (overlayImg.width / canvas.width),
                                selectionInOverlayY * (overlayImg.height / canvas.height),
                                selectionInOverlayWidth * (overlayImg.width / canvas.width),
                                selectionInOverlayHeight * (overlayImg.height / canvas.height),
                                0, 0, selection.width, selection.height);
            
            // Get image data
            const baseData = baseCanvas.toDataURL('image/png');
            const overlayData = overlayCanvas.toDataURL('image/png');
            
            // Send to server for comparison
            fetch('/compare_regions', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    base_image: baseData,
                    overlay_image: overlayData
                })
            })
            .then(response => response.json())
            .then(data => {
                // Display results
                document.getElementById('result').innerHTML = `
                    <h3>${data.result}</h3>
                    <p>Average Difference: ${data.avg_diff.toFixed(2)}</p>
                    <p>Analysis: ${data.description}</p>
                    <div>
                        <h4>Visualization</h4>
                        <img src="${data.diff_image}" width="400">
                    </div>
                `;
            })
            .catch(error => {
                console.error('Error:', error);
            });
        }
    </script>
</body>
</html>
    """)

@app.route("/compare_regions", methods=["POST"])
def compare_regions():
    data = request.json
    
    # Extract base64 image data
    base_data = data['base_image'].split(',')[1]
    overlay_data = data['overlay_image'].split(',')[1]
    
    # Convert to PIL images
    base_img = Image.open(io.BytesIO(base64.b64decode(base_data))).convert("RGB")
    overlay_img = Image.open(io.BytesIO(base64.b64decode(overlay_data))).convert("RGB")
    
    # Calculate difference
    diff = ImageChops.difference(base_img, overlay_img)
    
    # Get statistics
    stat = ImageStat.Stat(diff)
    avg_diff = sum(stat.mean) / len(stat.mean)
    
    # Convert difference to heatmap for visualization
    diff_array = np.array(diff)
    # Enhance contrast for better visualization
    diff_array = np.clip(diff_array * 3, 0, 255).astype(np.uint8)
    diff_heatmap = Image.fromarray(diff_array)
    
    # Create response with difference image
    buffered = io.BytesIO()
    diff_heatmap.save(buffered, format="PNG")
    diff_img_base64 = f"data:image/png;base64,{base64.b64encode(buffered.getvalue()).decode('utf-8')}"
    
    # Determine result
    high_threshold = 50
    med_threshold = 30
    
    if avg_diff > high_threshold:
        result = "Tampering Detected"
        description = "Significant differences found in the anti-tampering pattern. Verify carefully."
    elif avg_diff > med_threshold:
        result = "Possible Tampering Detected"
        description = "Some differences detected in the anti-tampering pattern. Further verification recommended."
    else:
        result = "No Tampering Detected"
        description = "The anti-tampering patterns match within acceptable parameters."
    
    return jsonify({
        "result": result,
        "avg_diff": avg_diff,
        "description": description,
        "diff_image": diff_img_base64
    })

if __name__ == "__main__":
    app.run(debug=True)
