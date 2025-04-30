import pygame
import sys
import json
import time
import threading

# Instead of importing from world_generator
def load_world(json_file):
    with open(json_file, 'r') as f:
        data = json.load(f)
    world = {loc['name']: loc for loc in data['locations']}
    return world

class RavenshadeUI:
    def __init__(self):
        # Initialize pygame
        pygame.init()
        self.screen = pygame.display.set_mode((960, 640))
        pygame.display.set_caption("Ravenshade Manor - Mystery Solver")
        self.clock = pygame.time.Clock()

        # Fonts and Colors
        self.font = pygame.font.SysFont("serif", 20)
        self.title_font = pygame.font.SysFont("serif", 30, bold=True)
        self.small_font = pygame.font.SysFont("serif", 16)
        self.WHITE = (255, 255, 255)
        self.BLACK = (0, 0, 0)
        self.GRAY = (200, 200, 200)
        self.DARKGRAY = (50, 50, 50)
        self.LIGHTGRAY = (150, 150, 150)
        self.HIGHLIGHT = (100, 150, 255)
        self.BUTTON_COLOR = (80, 80, 100)
        self.BUTTON_HOVER = (120, 120, 150)

        # Load the world from JSON
        try:
            self.world = load_world("world_content.json")
            self.current_location = list(self.world.keys())[0]  # Start in the first location
        except (FileNotFoundError, json.JSONDecodeError) as e:
            print(f"Error loading world data: {e}")
            self.world = {}
            self.current_location = None

        # UI State
        self.loading_images = False
        self.image_load_thread = None
        self.npc_images = {}
        self.location_images = {}
        self.hovered_npc = None
        self.show_options_menu = False
        self.show_move_menu = False
        self.narrative_text = "Welcome to Ravenshade Manor. Investigate the mystery by exploring and talking to characters."
        self.narrative_ready = True
        
        # Create placeholder images
        self.placeholder_image = pygame.Surface((150, 150))
        self.placeholder_image.fill(self.DARKGRAY)
        
        # Load any cached images
        self.preload_images()

    def preload_images(self):
        """Attempt to load any available images"""
        # In a real implementation, you'd load specific image files
        # This is a simplified placeholder approach
        if self.current_location and self.current_location in self.world:
            location = self.world[self.current_location]
            
            # Create placeholder for location
            if self.current_location not in self.location_images:
                self.location_images[self.current_location] = self.placeholder_image
            
            # Create placeholders for NPCs
            for npc in location.get('npcs', []):
                npc_name = npc['name']
                if npc_name not in self.npc_images:
                    self.npc_images[npc_name] = self.placeholder_image

    def start_image_loading(self):
        """Simulate image loading in a separate thread"""
        self.loading_images = True
        self.narrative_ready = False
        
        def load_images():
            time.sleep(1.5)  # Simulate loading time
            # In a real implementation, you'd load actual images here
            self.loading_images = False
            self.narrative_ready = True
        
        self.image_load_thread = threading.Thread(target=load_images)
        self.image_load_thread.daemon = True
        self.image_load_thread.start()

    def draw_text(self, text, pos, font, color=None, max_width=None):
        """Draw text with optional word wrapping"""
        if color is None:
            color = self.WHITE
            
        if max_width:
            words = text.split(' ')
            lines = []
            current_line = []
            
            for word in words:
                test_line = ' '.join(current_line + [word])
                if font.size(test_line)[0] <= max_width:
                    current_line.append(word)
                else:
                    if current_line:
                        lines.append(' '.join(current_line))
                    current_line = [word]
            
            if current_line:
                lines.append(' '.join(current_line))
        else:
            lines = text.split('\n')
            
        for i, line in enumerate(lines):
            txt_surf = font.render(line, True, color)
            self.screen.blit(txt_surf, (pos[0], pos[1] + i * (font.get_height() + 2)))
            
        return len(lines) * (font.get_height() + 2)

    def draw_button(self, rect, text, hover=False):
        """Draw a button with text"""
        color = self.BUTTON_HOVER if hover else self.BUTTON_COLOR
        pygame.draw.rect(self.screen, color, rect)
        pygame.draw.rect(self.screen, self.WHITE, rect, 1)
        
        txt_surf = self.font.render(text, True, self.WHITE)
        txt_rect = txt_surf.get_rect(center=rect.center)
        self.screen.blit(txt_surf, txt_rect)
        
        return rect

    def draw_npc(self, npc, pos, index):
        """Draw an NPC with hover effects"""
        npc_name = npc['name']
        
        # Check if we have an image for this NPC
        if npc_name in self.npc_images:
            img = self.npc_images[npc_name]
        else:
            img = self.placeholder_image
            self.npc_images[npc_name] = img
        
        # Draw image with border
        img_rect = img.get_rect(topleft=pos)
        is_hovered = self.hovered_npc == index
        border_color = self.HIGHLIGHT if is_hovered else self.WHITE
        
        # Draw image
        self.screen.blit(img, img_rect)
        pygame.draw.rect(self.screen, border_color, img_rect, 2)
        
        # Draw name
        name_y = pos[1] + img_rect.height + 5
        self.draw_text(npc_name, (pos[0], name_y), self.small_font)
        
        # Show hover info
        if is_hovered:
            info_rect = pygame.Rect(pos[0] + img_rect.width + 10, pos[1], 300, 150)
            pygame.draw.rect(self.screen, self.DARKGRAY, info_rect)
            pygame.draw.rect(self.screen, self.WHITE, info_rect, 1)
            
            description = npc.get('visual_description', 'No description available')
            self.draw_text(description, (info_rect.x + 10, info_rect.y + 10), 
                          self.small_font, max_width=280)
            
            interact_text = "Click to interact with this character"
            interact_y = info_rect.y + info_rect.height - 30
            self.draw_text(interact_text, (info_rect.x + 10, interact_y), 
                          self.small_font, color=self.HIGHLIGHT)
        
        return img_rect

    def draw_main_panel(self):
        """Draw the main game information panel"""
        if not self.current_location or self.current_location not in self.world:
            self.draw_text("Error: No location data available", (20, 20), self.title_font)
            return
            
        location = self.world[self.current_location]
        
        # Draw Title
        self.draw_text(location['name'], (20, 20), self.title_font)
        y_offset = 60
        
        # Draw loading indicator if images are loading
        if self.loading_images:
            loading_text = "Loading location assets..."
            self.draw_text(loading_text, (20, y_offset), self.font, color=self.LIGHTGRAY)
            y_offset += 30
        
        # Draw Description
        desc_height = self.draw_text(location['visual_description'], (20, y_offset), 
                                    self.font, max_width=920)
        y_offset += desc_height + 20
        
        # Draw Narrative panel
        narrative_rect = pygame.Rect(20, y_offset, 920, 100)
        pygame.draw.rect(self.screen, self.DARKGRAY, narrative_rect)
        pygame.draw.rect(self.screen, self.GRAY, narrative_rect, 1)
        
        if self.narrative_ready:
            narrative_text = self.narrative_text
        else:
            narrative_text = "Updating narrative..."
            
        self.draw_text(narrative_text, (narrative_rect.x + 10, narrative_rect.y + 10), 
                      self.font, max_width=900)
        y_offset += narrative_rect.height + 20
        
        # Draw NPCs
        self.draw_text("Characters Present:", (20, y_offset), self.font)
        y_offset += 30
        
        npc_x = 20
        for i, npc in enumerate(location.get('npcs', [])):
            npc_rect = self.draw_npc(npc, (npc_x, y_offset), i)
            npc_x += npc_rect.width + 20
        
        # Draw options button
        options_rect = pygame.Rect(800, 20, 140, 30)
        options_hover = self.show_options_menu
        self.draw_button(options_rect, "Options Menu", options_hover)
        
        # Draw options menu if active
        if self.show_options_menu:
            menu_rect = pygame.Rect(650, 55, 290, 180)
            pygame.draw.rect(self.screen, self.DARKGRAY, menu_rect)
            pygame.draw.rect(self.screen, self.WHITE, menu_rect, 1)
            
            # Menu title
            self.draw_text("Options", (menu_rect.x + 10, menu_rect.y + 10), self.font)
            
            # Move option
            move_rect = pygame.Rect(menu_rect.x + 20, menu_rect.y + 40, 250, 30)
            move_hover = self.show_move_menu
            self.draw_button(move_rect, "Move to...", move_hover)
            
            # Show movement submenu if active
            if self.show_move_menu:
                move_submenu = pygame.Rect(menu_rect.x + 300, menu_rect.y, 250, 30 + 
                                         len(location.get('connections', [])) * 35)
                pygame.draw.rect(self.screen, self.DARKGRAY, move_submenu)
                pygame.draw.rect(self.screen, self.WHITE, move_submenu, 1)
                
                self.draw_text("Select Location:", 
                              (move_submenu.x + 10, move_submenu.y + 10), self.font)
                
                for i, conn in enumerate(location.get('connections', [])):
                    conn_rect = pygame.Rect(move_submenu.x + 20, 
                                          move_submenu.y + 40 + i * 35, 
                                          210, 30)
                    self.draw_button(conn_rect, conn)
            
            # Examine option
            examine_rect = pygame.Rect(menu_rect.x + 20, menu_rect.y + 80, 250, 30)
            self.draw_button(examine_rect, "Examine room")
            
            # Inventory option
            inventory_rect = pygame.Rect(menu_rect.x + 20, menu_rect.y + 120, 250, 30)
            self.draw_button(inventory_rect, "View inventory")

    def handle_npc_click(self, npc_index):
        """Handle clicking on an NPC"""
        if self.current_location and self.current_location in self.world:
            location = self.world[self.current_location]
            npcs = location.get('npcs', [])
            
            if 0 <= npc_index < len(npcs):
                npc = npcs[npc_index]
                self.narrative_text = f"You approach {npc['name']}. They seem willing to talk."
                self.narrative_ready = False
                
                # In a real implementation, this would call the game engine
                # to get the NPC's dialogue options and response
                
                # Simulate narrative update delay
                def update_narrative():
                    time.sleep(1)
                    self.narrative_text = f"{npc['name']} says: \"I haven't seen anything unusual today, but you might want to investigate the library. Something strange is happening at the manor.\""
                    self.narrative_ready = True
                
                update_thread = threading.Thread(target=update_narrative)
                update_thread.daemon = True
                update_thread.start()

    def handle_location_change(self, new_location):
        """Handle changing locations"""
        if new_location in self.world:
            self.current_location = new_location
            self.show_options_menu = False
            self.show_move_menu = False
            self.narrative_ready = False
            self.narrative_text = f"Moving to {new_location}..."
            
            # Start loading images for the new location
            self.start_image_loading()
            
            # Simulate location change delay
            def update_location():
                time.sleep(1)
                self.narrative_text = f"You've arrived at {new_location}. {self.world[new_location]['visual_description']}"
                self.narrative_ready = True
            
            update_thread = threading.Thread(target=update_location)
            update_thread.daemon = True
            update_thread.start()

    def check_npc_hover(self, mouse_pos):
        """Check if mouse is hovering over an NPC"""
        if self.current_location and self.current_location in self.world:
            location = self.world[self.current_location]
            npcs = location.get('npcs', [])
            
            x = 20
            y_offset = 190  # Approximate y position where NPCs are drawn
            
            for i, npc in enumerate(npcs):
                img = self.npc_images.get(npc['name'], self.placeholder_image)
                img_rect = img.get_rect(topleft=(x, y_offset))
                
                if img_rect.collidepoint(mouse_pos):
                    self.hovered_npc = i
                    return
                    
                x += img_rect.width + 20
            
            self.hovered_npc = None

    def check_button_clicks(self, mouse_pos):
        """Handle button clicks"""
        # Options button
        options_rect = pygame.Rect(800, 20, 140, 30)
        if options_rect.collidepoint(mouse_pos):
            self.show_options_menu = not self.show_options_menu
            return True
        
        # If options menu is open
        if self.show_options_menu:
            menu_rect = pygame.Rect(650, 55, 290, 180)
            
            # Move button
            move_rect = pygame.Rect(menu_rect.x + 20, menu_rect.y + 40, 250, 30)
            if move_rect.collidepoint(mouse_pos):
                self.show_move_menu = not self.show_move_menu
                return True
            
            # Examine button
            examine_rect = pygame.Rect(menu_rect.x + 20, menu_rect.y + 80, 250, 30)
            if examine_rect.collidepoint(mouse_pos):
                self.narrative_text = f"You carefully examine the {self.current_location}..."
                self.narrative_ready = False
                
                def update_narrative():
                    time.sleep(1)
                    self.narrative_text = f"You notice some interesting details in the {self.current_location}. There seem to be clues here related to the mystery."
                    self.narrative_ready = True
                
                update_thread = threading.Thread(target=update_narrative)
                update_thread.daemon = True
                update_thread.start()
                
                return True
            
            # Inventory button
            inventory_rect = pygame.Rect(menu_rect.x + 20, menu_rect.y + 120, 250, 30)
            if inventory_rect.collidepoint(mouse_pos):
                self.narrative_text = "You check your inventory. You have a notebook, a pen, and a small flashlight."
                return True
            
            # If move submenu is open
            if self.show_move_menu and self.current_location in self.world:
                location = self.world[self.current_location]
                connections = location.get('connections', [])
                
                move_submenu = pygame.Rect(menu_rect.x + 300, menu_rect.y, 250, 30 + 
                                         len(connections) * 35)
                
                if move_submenu.collidepoint(mouse_pos):
                    for i, conn in enumerate(connections):
                        conn_rect = pygame.Rect(move_submenu.x + 20, 
                                              move_submenu.y + 40 + i * 35, 
                                              210, 30)
                        if conn_rect.collidepoint(mouse_pos):
                            self.handle_location_change(conn)
                            return True
        
        return False

    def run(self):
        """Main game loop"""
        running = True
        
        # Preload initial images
        self.start_image_loading()
        
        while running:
            self.screen.fill(self.BLACK)
            mouse_pos = pygame.mouse.get_pos()
            
            # Check for NPC hover
            self.check_npc_hover(mouse_pos)
            
            # Draw the main UI
            self.draw_main_panel()

            # Event Handling
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    running = False
                    
                elif event.type == pygame.MOUSEBUTTONDOWN:
                    if event.button == 1:  # Left click
                        # Check if an NPC was clicked
                        if self.hovered_npc is not None:
                            self.handle_npc_click(self.hovered_npc)
                        else:
                            # Check for button clicks
                            self.check_button_clicks(event.pos)

            pygame.display.flip()
            self.clock.tick(30)

        pygame.quit()
        sys.exit()


if __name__ == "__main__":
    ui = RavenshadeUI()
    ui.run()
