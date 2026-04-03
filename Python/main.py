from agent import Agent
import paramiko

agent = Agent("192.168.0.10")
agent.open_ssh_connection()