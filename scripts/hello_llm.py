from adas_agent.llm import get_llm

llm = get_llm()
response = llm.invoke("用一句话解释什么是 ADAS 功能降级。")

print("回复:", response.content)
print("Token 用量:", response.usage_metadata)