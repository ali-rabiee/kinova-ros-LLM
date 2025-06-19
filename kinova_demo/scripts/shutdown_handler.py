#!/usr/bin/env python3

import rospy
import subprocess
import sys
import threading
import select
from std_msgs.msg import String

class SimulationShutdownHandler:
    def __init__(self):
        rospy.init_node('simulation_shutdown_handler', anonymous=True)
        
        # Subscribe to shutdown topic
        self.shutdown_sub = rospy.Subscriber('/kinova_sim/shutdown', String, self.shutdown_callback)
        
        # Publisher for status messages
        self.status_pub = rospy.Publisher('/kinova_sim/status', String, queue_size=1)
        
        self.shutdown_requested = False
        
        # Display instructions
        self.print_instructions()
        
        # Start keyboard monitoring in separate thread
        self.keyboard_thread = threading.Thread(target=self.monitor_keyboard)
        self.keyboard_thread.daemon = True
        self.keyboard_thread.start()
        
        rospy.loginfo("🛡️  Shutdown handler ready! Use 'q' + ENTER or publish to /kinova_sim/shutdown")

    def print_instructions(self):
        print("\n" + "="*60)
        print("🛡️  KINOVA SIMULATION SHUTDOWN HANDLER ACTIVE")
        print("="*60)
        print("📋 SHUTDOWN OPTIONS:")
        print("   1️⃣  Press 'q' + ENTER in this terminal")
        print("   2️⃣  Press 'quit' + ENTER in this terminal") 
        print("   3️⃣  Press 'stop' + ENTER in this terminal")
        print("   4️⃣  Publish: rostopic pub /kinova_sim/shutdown std_msgs/String 'shutdown'")
        print("   5️⃣  Emergency: Ctrl+C (but prefer options above)")
        print("="*60)
        print("💡 This handler will cleanly stop Gazebo, MoveIt, and all nodes")
        print("="*60 + "\n")

    def monitor_keyboard(self):
        """Monitor keyboard input in separate thread"""
        while not rospy.is_shutdown() and not self.shutdown_requested:
            try:
                # Check if there's input available
                if select.select([sys.stdin], [], [], 0.1)[0]:
                    user_input = sys.stdin.readline().strip().lower()
                    if user_input in ['q', 'quit', 'stop', 'exit']:
                        rospy.loginfo(f"🔥 Shutdown triggered by keyboard: '{user_input}'")
                        self.initiate_shutdown()
                        break
            except Exception as e:
                # Handle any input errors gracefully
                pass

    def shutdown_callback(self, msg):
        """Handle shutdown request from ROS topic"""
        rospy.loginfo(f"🔥 Shutdown triggered by topic: '{msg.data}'")
        self.initiate_shutdown()

    def initiate_shutdown(self):
        """Perform graceful shutdown of all simulation components"""
        if self.shutdown_requested:
            return
            
        self.shutdown_requested = True
        
        rospy.loginfo("🛑 INITIATING GRACEFUL SHUTDOWN...")
        self.status_pub.publish(String("SHUTDOWN_INITIATED"))
        
        try:
            # Step 1: Kill ROS launch processes
            rospy.loginfo("🔄 Step 1: Stopping ROS launch processes...")
            subprocess.run(['pkill', '-f', 'roslaunch'], check=False)
            rospy.sleep(1)
            
            # Step 2: Kill Gazebo
            rospy.loginfo("🔄 Step 2: Stopping Gazebo...")
            subprocess.run(['killall', 'gzserver', 'gzclient', 'gazebo'], 
                          check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            rospy.sleep(1)
            
            # Step 3: Kill MoveIt nodes
            rospy.loginfo("🔄 Step 3: Stopping MoveIt nodes...")
            subprocess.run(['pkill', '-f', 'move_group'], check=False)
            rospy.sleep(1)
            
            # Step 4: Kill other ROS nodes
            rospy.loginfo("🔄 Step 4: Stopping remaining ROS nodes...")
            subprocess.run(['pkill', '-f', 'kinova'], check=False)
            subprocess.run(['pkill', '-f', 'rviz'], check=False)
            rospy.sleep(1)
            
            # Step 5: Final cleanup
            rospy.loginfo("🔄 Step 5: Final cleanup...")
            subprocess.run(['pkill', '-f', 'ros'], check=False)
            
            rospy.loginfo("✅ SHUTDOWN COMPLETE! All processes stopped.")
            self.status_pub.publish(String("SHUTDOWN_COMPLETE"))
            
            print("\n" + "="*60)
            print("✅ KINOVA SIMULATION CLEANLY SHUT DOWN")
            print("="*60)
            print("💡 You can now:")
            print("   • Run the simulation again")
            print("   • Close this terminal safely")
            print("   • Start other ROS applications")
            print("="*60 + "\n")
            
        except Exception as e:
            rospy.logerr(f"❌ Error during shutdown: {e}")
            
        finally:
            # Shutdown this node
            rospy.signal_shutdown("Shutdown complete")

    def run(self):
        """Main run loop"""
        rospy.loginfo("🚀 Shutdown handler running...")
        try:
            rospy.spin()
        except KeyboardInterrupt:
            rospy.loginfo("🔥 Shutdown triggered by Ctrl+C")
            self.initiate_shutdown()

if __name__ == '__main__':
    try:
        handler = SimulationShutdownHandler()
        handler.run()
    except rospy.ROSInterruptException:
        pass 