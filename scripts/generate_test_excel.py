import pandas as pd
import os

# 创建测试数据 - 商家评论示例
data = {
    'shop_name': ['星巴克', '肯德基', '麦当劳', '海底捞', '西贝莜面村'],
    'review_content': [
        '咖啡很香,环境舒适,适合学习办公',
        '汉堡好吃,价格实惠,服务速度快',
        '薯条酥脆,汉堡新鲜,适合快餐',
        '服务态度超好,菜品新鲜,性价比高',
        '西北特色美食,羊肉串很正宗,环境干净'
    ],
    'rating': [5, 4, 4, 5, 4],
    'reviewer': ['张三', '李四', '王五', '赵六', '孙七'],
    'location': ['北京', '上海', '广州', '深圳', '杭州']
}

df = pd.DataFrame(data)

# 保存为 Excel
output_dir = 'test_files'
os.makedirs(output_dir, exist_ok=True)
excel_path = os.path.join(output_dir, 'shop_reviews_test.xlsx')
csv_path = os.path.join(output_dir, 'shop_reviews_test.csv')

df.to_excel(excel_path, index=False, engine='openpyxl')
df.to_csv(csv_path, index=False, encoding='utf-8-sig')

print(f"✅ 测试文件已生成:")
print(f"  - Excel: {excel_path}")
print(f"  - CSV: {csv_path}")
print(f"\n📊 数据预览:")
print(df)
