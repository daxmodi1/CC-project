import cv2
import numpy as np
import json
import random

def generate_animation_script(job_id: str, num_frames: int, num_balls: int = 5, width: int = 800, height: int = 600):
    """
    Generates a JSON script containing the trajectories of bouncing balls.
    """
    script = {
        "job_id": job_id,
        "width": width,
        "height": height,
        "num_frames": num_frames,
        "frames": []
    }
    
    # Initialize ball positions and velocities
    balls = []
    for i in range(num_balls):
        balls.append({
            "id": i,
            "x": random.randint(50, width - 50),
            "y": random.randint(50, height - 50),
            "vx": random.choice([-5, -4, -3, 3, 4, 5]),
            "vy": random.choice([-5, -4, -3, 3, 4, 5]),
            "radius": random.randint(15, 40),
            "color": (random.randint(50, 255), random.randint(50, 255), random.randint(50, 255))
        })
        
    for frame_idx in range(num_frames):
        frame_data = {"frame_index": frame_idx, "objects": []}
        for b in balls:
            # Move the ball
            b["x"] += b["vx"]
            b["y"] += b["vy"]
            
            # Bounce off walls
            if b["x"] - b["radius"] <= 0 or b["x"] + b["radius"] >= width:
                b["vx"] *= -1
                b["x"] = max(b["radius"], min(b["x"], width - b["radius"]))
            if b["y"] - b["radius"] <= 0 or b["y"] + b["radius"] >= height:
                b["vy"] *= -1
                b["y"] = max(b["radius"], min(b["y"], height - b["radius"]))
                
            frame_data["objects"].append({
                "id": b["id"],
                "x": b["x"],
                "y": b["y"],
                "radius": b["radius"],
                "color": b["color"]
            })
            
        script["frames"].append(frame_data)
        
    return script

def render_frame(script_data: dict, frame_index: int, output_path: str):
    """
    Renders a single frame using OpenCV based on the JSON script.
    """
    width = script_data["width"]
    height = script_data["height"]
    
    # Create a dark background image
    image = np.zeros((height, width, 3), dtype=np.uint8)
    image[:] = (30, 30, 30) # Dark gray background
    
    # Find the data for this specific frame
    frame_data = next((f for f in script_data["frames"] if f["frame_index"] == frame_index), None)
    if not frame_data:
        raise ValueError(f"Frame {frame_index} not found in script.")
        
    # Draw the objects
    for obj in frame_data["objects"]:
        center = (int(obj["x"]), int(obj["y"]))
        radius = int(obj["radius"])
        color = tuple(obj["color"]) # OpenCV uses BGR, but it's random anyway so it's fine
        
        # Draw a filled circle with anti-aliasing
        cv2.circle(image, center, radius, color, -1, cv2.LINE_AA)
        # Draw a white outline
        cv2.circle(image, center, radius, (255, 255, 255), 2, cv2.LINE_AA)
        
    # Add text overlay
    text = f"Job: {script_data['job_id']} | Frame: {frame_index}"
    cv2.putText(image, text, (20, 40), cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 255, 255), 2, cv2.LINE_AA)
        
    # Save the image
    cv2.imwrite(output_path, image)
    return output_path
