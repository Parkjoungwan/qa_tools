# plot_mem_usage.py

import os
import re
from datetime import datetime
import matplotlib.pyplot as plt
import pandas as pd

def read_last_lines(filename, num_lines=30):
    with open(filename, 'r', encoding='utf-8') as f:
        lines = f.readlines()
        return lines[-num_lines:]

def parse_log_lines(lines):
    pattern = r"\[(.*?)\] MEM ([0-9.]+)%"
    data = []
    for line in lines:
        match = re.search(pattern, line)
        if match:
            timestamp_str, mem_percent = match.groups()
            try:
                timestamp = datetime.strptime(timestamp_str, "%Y-%m-%d %H:%M:%S")
                data.append((timestamp, float(mem_percent)))
            except ValueError:
                continue
    return pd.DataFrame(data, columns=["time", "mem_usage"])

def plot_memory_usage(df):
    if df.empty:
        print("⚠️ 유효한 로그 데이터가 없습니다.")
        return
    plt.figure(figsize=(12, 6))
    plt.plot(df["time"], df["mem_usage"], marker='o')
    plt.title("Memory Usage (Last 30 Entries)")
    plt.xlabel("Time")
    plt.ylabel("Memory Usage (%)")
    plt.xticks(rotation=45)
    plt.grid(True)
    plt.tight_layout()
    plt.show()

def main():
    log_path = os.path.join(os.getcwd(), "monitor.log")
    if not os.path.exists(log_path):
        print("❌ monitor.log 파일이 현재 디렉토리에 없습니다.")
        return

    lines = read_last_lines(log_path, 30)
    df = parse_log_lines(lines)
    plot_memory_usage(df)

if __name__ == "__main__":
    main()

