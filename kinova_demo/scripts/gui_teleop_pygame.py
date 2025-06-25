#!/usr/bin/env python3
"""
Advanced Pygame-based GUI Teleop for Kinova Robot
Clean, modern interface with proper mode switching
Compatible with Gazebo trajectory controllers
"""

import sys
import os
import rospy
import pygame
import numpy as np
from threading import Lock, Timer
from enum import Enum

# ROS message imports
from trajectory_msgs.msg import JointTrajectory, JointTrajectoryPoint
from sensor_msgs.msg import JointState

# Initialize pygame
pygame.init()

class TeleopMode(Enum):
    """Control modes for the teleop interface"""
    TRANSLATION = "TRANSLATION"
    ROTATION = "ROTATION" 
    GRIPPER = "GRIPPER"

class Colors:
    """Color constants for the GUI"""
    BLACK = (0, 0, 0)
    WHITE = (255, 255, 255)
    GRAY = (128, 128, 128)
    LIGHT_GRAY = (200, 200, 200)
    DARK_GRAY = (64, 64, 64)
    RED = (255, 0, 0)
    GREEN = (0, 255, 0)
    BLUE = (0, 0, 255)
    YELLOW = (255, 255, 0)
    ORANGE = (255, 165, 0)
    PURPLE = (128, 0, 128)
    CYAN = (0, 255, 255)
    
    # Mode colors
    TRANSLATION_COLOR = (0, 150, 255)  # Blue
    ROTATION_COLOR = (255, 100, 0)     # Orange
    GRIPPER_COLOR = (0, 200, 0)        # Green
    
    # Button states
    BUTTON_NORMAL = (100, 100, 100)
    BUTTON_HOVER = (150, 150, 150)
    BUTTON_PRESSED = (200, 200, 200)
    BUTTON_ACTIVE = (255, 255, 100)

class Button:
    """Advanced button class with hover and press states"""
    
    def __init__(self, x, y, width, height, text, color=Colors.BUTTON_NORMAL, text_color=Colors.WHITE, font_size=16):
        self.rect = pygame.Rect(x, y, width, height)
        self.text = text
        self.color = color
        self.text_color = text_color
        self.font = pygame.font.Font(None, font_size)
        self.is_hovered = False
        self.is_pressed = False
        self.is_active = False
        
    def draw(self, screen):
        """Draw the button with appropriate state"""
        # Determine color based on state
        if self.is_pressed:
            current_color = Colors.BUTTON_PRESSED
        elif self.is_active:
            current_color = Colors.BUTTON_ACTIVE
        elif self.is_hovered:
            current_color = Colors.BUTTON_HOVER
        else:
            current_color = self.color
            
        # Draw button background
        pygame.draw.rect(screen, current_color, self.rect)
        pygame.draw.rect(screen, Colors.WHITE, self.rect, 2)
        
        # Draw text centered
        text_surface = self.font.render(self.text, True, self.text_color)
        text_rect = text_surface.get_rect(center=self.rect.center)
        screen.blit(text_surface, text_rect)
        
    def handle_event(self, event):
        """Handle mouse events"""
        if event.type == pygame.MOUSEMOTION:
            self.is_hovered = self.rect.collidepoint(event.pos)
        elif event.type == pygame.MOUSEBUTTONDOWN:
            if self.rect.collidepoint(event.pos):
                self.is_pressed = True
                return 'press'
        elif event.type == pygame.MOUSEBUTTONUP:
            if self.is_pressed:
                self.is_pressed = False
                if self.rect.collidepoint(event.pos):
                    return 'click'
        return None

class KinovaController:
    """Enhanced Kinova controller for pygame GUI using trajectory controllers"""
    
    def __init__(self):
        # ROS setup
        rospy.init_node('kinova_pygame_teleop', anonymous=True)
        
        # Publishers - using trajectory controllers that are actually loaded
        self.arm_traj_pub = rospy.Publisher('/j2n6s300/effort_joint_trajectory_controller/command', 
                                           JointTrajectory, queue_size=1)
        self.finger_traj_pub = rospy.Publisher('/j2n6s300/effort_finger_trajectory_controller/command', 
                                              JointTrajectory, queue_size=1)
        
        # Subscribers
        self.joint_sub = rospy.Subscriber('/j2n6s300/joint_states', JointState, self.joint_state_callback)
        
        # Control parameters
        self.linear_scale = 0.1    # Reduced for smoother control
        self.angular_scale = 0.2   # Reduced for smoother control
        self.gripper_scale = 0.3   # Reduced for smoother control
        self.publish_rate = 10     # Hz - trajectory controllers prefer slower rates
        
        # Joint names
        self.arm_joint_names = [
            'j2n6s300_joint_1', 'j2n6s300_joint_2', 'j2n6s300_joint_3',
            'j2n6s300_joint_4', 'j2n6s300_joint_5', 'j2n6s300_joint_6'
        ]
        self.finger_joint_names = [
            'j2n6s300_joint_finger_1', 'j2n6s300_joint_finger_2', 'j2n6s300_joint_finger_3'
        ]
        
        # State tracking
        self.current_mode = TeleopMode.TRANSLATION
        self.active_commands = {}
        self.command_lock = Lock()
        self.is_publishing = False
        self.command_timer = None
        
        # Joint states
        self.current_joint_positions = [0.0] * 6
        self.current_finger_positions = [0.0] * 3
        self.joint_lock = Lock()
        
        rospy.loginfo("Kinova Pygame Controller initialized with trajectory controllers")
        
    def joint_state_callback(self, msg):
        """Update current joint positions"""
        with self.joint_lock:
            # Update arm joints
            for i, name in enumerate(self.arm_joint_names):
                if name in msg.name:
                    idx = msg.name.index(name)
                    if i < len(self.current_joint_positions):
                        self.current_joint_positions[i] = msg.position[idx]
                        
            # Update finger joints
            for i, name in enumerate(self.finger_joint_names):
                if name in msg.name:
                    idx = msg.name.index(name)
                    if i < len(self.current_finger_positions):
                        self.current_finger_positions[i] = msg.position[idx]
    
    def set_mode(self, mode):
        """Change control mode"""
        with self.command_lock:
            self.current_mode = mode
            self.active_commands.clear()
        self.stop_publishing()
        rospy.loginfo(f"Mode changed to: {mode.value}")
        
    def start_command(self, axis, value):
        """Start a continuous command"""
        with self.command_lock:
            self.active_commands[axis] = value
        self.start_publishing()
        
    def stop_command(self, axis):
        """Stop a specific command"""
        with self.command_lock:
            if axis in self.active_commands:
                del self.active_commands[axis]
        if not self.active_commands:
            self.stop_publishing()
            
    def stop_all_commands(self):
        """Emergency stop"""
        with self.command_lock:
            self.active_commands.clear()
        self.stop_publishing()
        
    def start_publishing(self):
        """Start publishing commands"""
        if not self.is_publishing:
            self.is_publishing = True
            self._publish_loop()
            
    def stop_publishing(self):
        """Stop publishing"""
        self.is_publishing = False
        if self.command_timer:
            self.command_timer.cancel()
        
    def _publish_loop(self):
        """Publishing loop"""
        if self.is_publishing and self.active_commands:
            self._publish_commands()
            # Schedule next publish
            self.command_timer = Timer(1.0/self.publish_rate, self._publish_loop)
            self.command_timer.start()
        else:
            self.is_publishing = False
            
    def _publish_commands(self):
        """Publish current commands"""
        with self.command_lock:
            if not self.active_commands:
                return
            mode = self.current_mode
            commands = self.active_commands.copy()
            
        if mode == TeleopMode.GRIPPER:
            self._publish_gripper_commands(commands)
        else:
            self._publish_arm_commands(mode, commands)
    
    def _create_arm_trajectory(self, target_positions):
        """Create a JointTrajectory message for arm movement"""
        traj = JointTrajectory()
        traj.header.stamp = rospy.Time.now()
        traj.joint_names = self.arm_joint_names
        
        point = JointTrajectoryPoint()
        point.positions = target_positions
        point.velocities = [0.0] * 6
        point.accelerations = [0.0] * 6
        point.time_from_start = rospy.Duration(0.2)  # 200ms trajectory
        
        traj.points = [point]
        return traj
    
    def _create_finger_trajectory(self, target_positions):
        """Create a JointTrajectory message for finger movement"""
        traj = JointTrajectory()
        traj.header.stamp = rospy.Time.now()
        traj.joint_names = self.finger_joint_names
        
        point = JointTrajectoryPoint()
        point.positions = target_positions
        point.velocities = [0.0] * 3
        point.accelerations = [0.0] * 3
        point.time_from_start = rospy.Duration(0.2)  # 200ms trajectory
        
        traj.points = [point]
        return traj
            
    def _publish_arm_commands(self, mode, commands):
        """Publish arm trajectory commands"""
        with self.joint_lock:
            current_positions = self.current_joint_positions.copy()
        
        # Calculate incremental position changes
        position_deltas = [0.0] * 6
        
        if mode == TeleopMode.TRANSLATION:
            # Simplified cartesian to joint mapping
            x_delta = commands.get('x', 0.0) * self.linear_scale
            y_delta = commands.get('y', 0.0) * self.linear_scale
            z_delta = commands.get('z', 0.0) * self.linear_scale
            
            position_deltas[0] = -y_delta  # Base rotation
            position_deltas[1] = -z_delta  # Shoulder
            position_deltas[2] = z_delta   # Elbow
            position_deltas[3] = x_delta   # Wrist 1
            
        elif mode == TeleopMode.ROTATION:
            # Wrist rotations
            rx_delta = commands.get('rx', 0.0) * self.angular_scale
            ry_delta = commands.get('ry', 0.0) * self.angular_scale
            rz_delta = commands.get('rz', 0.0) * self.angular_scale
            
            position_deltas[3] = rx_delta  # Wrist 1
            position_deltas[4] = ry_delta  # Wrist 2
            position_deltas[5] = rz_delta  # Wrist 3
        
        # Calculate target positions
        target_positions = [current_positions[i] + position_deltas[i] for i in range(6)]
        
        # Create and publish trajectory
        traj = self._create_arm_trajectory(target_positions)
        self.arm_traj_pub.publish(traj)
        
    def _publish_gripper_commands(self, commands):
        """Publish gripper trajectory commands"""
        with self.joint_lock:
            current_positions = self.current_finger_positions.copy()
        
        # Calculate target finger positions
        target_positions = current_positions.copy()
        
        if 'open' in commands:
            # Open gripper (negative positions)
            delta = -self.gripper_scale
            target_positions = [pos + delta for pos in current_positions]
        elif 'close' in commands:
            # Close gripper (positive positions)
            delta = self.gripper_scale
            target_positions = [pos + delta for pos in current_positions]
        
        # Create and publish trajectory
        traj = self._create_finger_trajectory(target_positions)
        self.finger_traj_pub.publish(traj)

class PygameGUI:
    """Advanced Pygame GUI for Kinova teleop"""
    
    def __init__(self):
        # Screen setup
        self.screen_width = 800
        self.screen_height = 600
        self.screen = pygame.display.set_mode((self.screen_width, self.screen_height))
        pygame.display.set_caption("Kinova Advanced Teleop Control")
        
        # Fonts
        self.title_font = pygame.font.Font(None, 36)
        self.mode_font = pygame.font.Font(None, 28)
        self.button_font = pygame.font.Font(None, 20)
        self.info_font = pygame.font.Font(None, 16)
        
        # Controller
        self.controller = KinovaController()
        
        # GUI state
        self.current_mode = TeleopMode.TRANSLATION
        self.buttons = {}
        self.active_buttons = set()
        self.running = True
        self.clock = pygame.time.Clock()
        
        # Create buttons
        self.create_buttons()
        
        rospy.loginfo("Pygame GUI initialized")
        
    def get_mode_color(self, mode):
        """Get color for current mode"""
        if mode == TeleopMode.TRANSLATION:
            return Colors.TRANSLATION_COLOR
        elif mode == TeleopMode.ROTATION:
            return Colors.ROTATION_COLOR
        elif mode == TeleopMode.GRIPPER:
            return Colors.GRIPPER_COLOR
        return Colors.GRAY
        
    def create_buttons(self):
        """Create all buttons"""
        self.buttons.clear()
        
        # Mode switch button
        self.buttons['mode_switch'] = Button(
            350, 80, 100, 40, "Switch Mode", Colors.PURPLE, Colors.WHITE, 18
        )
        
        # Emergency stop
        self.buttons['emergency'] = Button(
            350, 520, 100, 50, "EMERGENCY\nSTOP", Colors.RED, Colors.WHITE, 16
        )
        
        # Control buttons based on mode
        if self.current_mode == TeleopMode.TRANSLATION:
            self.create_translation_buttons()
        elif self.current_mode == TeleopMode.ROTATION:
            self.create_rotation_buttons()
        elif self.current_mode == TeleopMode.GRIPPER:
            self.create_gripper_buttons()
            
    def create_translation_buttons(self):
        """Create translation control buttons"""
        button_width, button_height = 120, 50
        
        # X axis
        self.buttons['x_pos'] = Button(450, 180, button_width, button_height, "+X Forward", Colors.TRANSLATION_COLOR)
        self.buttons['x_neg'] = Button(250, 180, button_width, button_height, "-X Back", Colors.TRANSLATION_COLOR)
        
        # Y axis  
        self.buttons['y_pos'] = Button(450, 250, button_width, button_height, "+Y Left", Colors.TRANSLATION_COLOR)
        self.buttons['y_neg'] = Button(250, 250, button_width, button_height, "-Y Right", Colors.TRANSLATION_COLOR)
        
        # Z axis
        self.buttons['z_pos'] = Button(450, 320, button_width, button_height, "+Z Up", Colors.TRANSLATION_COLOR)
        self.buttons['z_neg'] = Button(250, 320, button_width, button_height, "-Z Down", Colors.TRANSLATION_COLOR)
        
    def create_rotation_buttons(self):
        """Create rotation control buttons"""
        button_width, button_height = 120, 50
        
        # Roll
        self.buttons['rx_pos'] = Button(450, 180, button_width, button_height, "+Roll", Colors.ROTATION_COLOR)
        self.buttons['rx_neg'] = Button(250, 180, button_width, button_height, "-Roll", Colors.ROTATION_COLOR)
        
        # Pitch
        self.buttons['ry_pos'] = Button(450, 250, button_width, button_height, "+Pitch", Colors.ROTATION_COLOR)
        self.buttons['ry_neg'] = Button(250, 250, button_width, button_height, "-Pitch", Colors.ROTATION_COLOR)
        
        # Yaw
        self.buttons['rz_pos'] = Button(450, 320, button_width, button_height, "+Yaw", Colors.ROTATION_COLOR)
        self.buttons['rz_neg'] = Button(250, 320, button_width, button_height, "-Yaw", Colors.ROTATION_COLOR)
        
    def create_gripper_buttons(self):
        """Create gripper control buttons"""
        button_width, button_height = 150, 80
        
        self.buttons['gripper_open'] = Button(200, 200, button_width, button_height, "OPEN\nGRIPPER", Colors.GRIPPER_COLOR)
        self.buttons['gripper_close'] = Button(450, 200, button_width, button_height, "CLOSE\nGRIPPER", Colors.GRIPPER_COLOR)
        
    def switch_mode(self):
        """Switch to next mode"""
        modes = [TeleopMode.TRANSLATION, TeleopMode.ROTATION, TeleopMode.GRIPPER]
        current_index = modes.index(self.current_mode)
        next_index = (current_index + 1) % len(modes)
        
        old_mode = self.current_mode
        self.current_mode = modes[next_index]
        
        # Update controller
        self.controller.set_mode(self.current_mode)
        
        # Recreate buttons
        self.active_buttons.clear()
        self.create_buttons()
        
        rospy.loginfo(f"GUI Mode switched: {old_mode.value} → {self.current_mode.value}")
        
    def handle_button_press(self, button_name):
        """Handle button press events"""
        if button_name == 'mode_switch':
            self.switch_mode()
        elif button_name == 'emergency':
            self.controller.stop_all_commands()
            self.active_buttons.clear()
        elif button_name.startswith('x_'):
            axis, direction = 'x', 1 if 'pos' in button_name else -1
            self.controller.start_command(axis, direction)
            self.active_buttons.add(button_name)
        elif button_name.startswith('y_'):
            axis, direction = 'y', 1 if 'pos' in button_name else -1
            self.controller.start_command(axis, direction)
            self.active_buttons.add(button_name)
        elif button_name.startswith('z_'):
            axis, direction = 'z', 1 if 'pos' in button_name else -1
            self.controller.start_command(axis, direction)
            self.active_buttons.add(button_name)
        elif button_name.startswith('rx_'):
            axis, direction = 'rx', 1 if 'pos' in button_name else -1
            self.controller.start_command(axis, direction)
            self.active_buttons.add(button_name)
        elif button_name.startswith('ry_'):
            axis, direction = 'ry', 1 if 'pos' in button_name else -1
            self.controller.start_command(axis, direction)
            self.active_buttons.add(button_name)
        elif button_name.startswith('rz_'):
            axis, direction = 'rz', 1 if 'pos' in button_name else -1
            self.controller.start_command(axis, direction)
            self.active_buttons.add(button_name)
        elif button_name == 'gripper_open':
            self.controller.start_command('open', 1.0)
            self.active_buttons.add(button_name)
        elif button_name == 'gripper_close':
            self.controller.start_command('close', 1.0)
            self.active_buttons.add(button_name)
            
    def handle_button_release(self, button_name):
        """Handle button release events"""
        if button_name in self.active_buttons:
            self.active_buttons.remove(button_name)
            
            # Stop corresponding command
            if button_name.startswith('x_'):
                self.controller.stop_command('x')
            elif button_name.startswith('y_'):
                self.controller.stop_command('y')
            elif button_name.startswith('z_'):
                self.controller.stop_command('z')
            elif button_name.startswith('rx_'):
                self.controller.stop_command('rx')
            elif button_name.startswith('ry_'):
                self.controller.stop_command('ry')
            elif button_name.startswith('rz_'):
                self.controller.stop_command('rz')
            elif button_name == 'gripper_open':
                self.controller.stop_command('open')
            elif button_name == 'gripper_close':
                self.controller.stop_command('close')
                
    def draw_header(self):
        """Draw the header section"""
        # Title
        title_text = self.title_font.render("Kinova Advanced Teleop", True, Colors.WHITE)
        title_rect = title_text.get_rect(center=(self.screen_width // 2, 30))
        self.screen.blit(title_text, title_rect)
        
        # Current mode with colored background
        mode_color = self.get_mode_color(self.current_mode)
        mode_bg_rect = pygame.Rect(250, 50, 300, 35)
        pygame.draw.rect(self.screen, mode_color, mode_bg_rect)
        pygame.draw.rect(self.screen, Colors.WHITE, mode_bg_rect, 2)
        
        mode_text = self.mode_font.render(f"Mode: {self.current_mode.value}", True, Colors.WHITE)
        mode_rect = mode_text.get_rect(center=mode_bg_rect.center)
        self.screen.blit(mode_text, mode_rect)
        
    def draw_instructions(self):
        """Draw instruction text"""
        instructions = [
            "Hold buttons to move, release to stop",
            "Use 'Switch Mode' to cycle through control modes",
            "Red button for emergency stop"
        ]
        
        y_offset = 420
        for instruction in instructions:
            inst_text = self.info_font.render(instruction, True, Colors.LIGHT_GRAY)
            inst_rect = inst_text.get_rect(center=(self.screen_width // 2, y_offset))
            self.screen.blit(inst_text, inst_rect)
            y_offset += 20
            
    def draw_status(self):
        """Draw robot status information"""
        # Joint positions (simplified display)
        with self.controller.joint_lock:
            joint_pos = self.controller.current_joint_positions.copy()
            finger_pos = self.controller.current_finger_positions.copy()
            
        status_text = f"Joints: {[f'{p:.2f}' for p in joint_pos[:3]]}... | Fingers: {[f'{p:.2f}' for p in finger_pos]}"
        status_surface = self.info_font.render(status_text, True, Colors.LIGHT_GRAY)
        self.screen.blit(status_surface, (10, self.screen_height - 25))
        
        # Active commands
        active_text = f"Active: {len(self.active_buttons)} commands"
        active_surface = self.info_font.render(active_text, True, Colors.YELLOW)
        self.screen.blit(active_surface, (10, self.screen_height - 45))
        
    def run(self):
        """Main game loop"""
        rospy.loginfo("Starting Pygame GUI main loop")
        
        while self.running and not rospy.is_shutdown():
            # Handle events
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    self.running = False
                elif event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_ESCAPE:
                        self.running = False
                    elif event.key == pygame.K_SPACE:
                        self.switch_mode()
                        
                # Handle button events - use copy to avoid dictionary modification during iteration
                for button_name, button in list(self.buttons.items()):
                    result = button.handle_event(event)
                    if result == 'press':
                        self.handle_button_press(button_name)
                    elif result == 'click':
                        self.handle_button_release(button_name)
                        
            # Update button states - use copy to avoid dictionary modification during iteration
            for button_name, button in list(self.buttons.items()):
                button.is_active = button_name in self.active_buttons
                
            # Draw everything
            self.screen.fill(Colors.BLACK)
            
            self.draw_header()
            self.draw_instructions()
            self.draw_status()
            
            # Draw buttons
            for button in self.buttons.values():
                button.draw(self.screen)
                
            pygame.display.flip()
            self.clock.tick(60)  # 60 FPS
            
        # Cleanup
        self.controller.stop_all_commands()
        pygame.quit()
        rospy.loginfo("Pygame GUI closed")

def main():
    """Main function"""
    try:
        gui = PygameGUI()
        gui.run()
    except KeyboardInterrupt:
        rospy.loginfo("Interrupted by user")
    except Exception as e:
        rospy.logerr(f"Error: {e}")
        
if __name__ == '__main__':
    main() 