import cv2
import numpy as np
import os

class CoordinateMarker:
    def __init__(self):
        self.drawing = False
        self.start_x = -1
        self.start_y = -1
        self.image = None
        self.original_size = None
        self.scale = 1.0
        self.window_name = "Image Coordinate Marker"
        self.coordinates = []
        
    def mouse_callback(self, event, x, y, flags, param):
        if event == cv2.EVENT_LBUTTONDOWN:
            self.drawing = True
            self.start_x, self.start_y = x, y
            
        elif event == cv2.EVENT_MOUSEMOVE:
            if self.drawing:
                img_copy = self.image.copy()
                cv2.rectangle(img_copy, (self.start_x, self.start_y), (x, y), (0, 255, 0), 2)
                cv2.imshow(self.window_name, img_copy)
                
        elif event == cv2.EVENT_LBUTTONUP:
            self.drawing = False
            # 记录坐标，确保左上和右下的顺序正确
            x1, x2 = min(self.start_x, x), max(self.start_x, x)
            y1, y2 = min(self.start_y, y), max(self.start_y, y)
            
            # 转换回原始图片的坐标
            orig_x1 = int(x1 / self.scale)
            orig_y1 = int(y1 / self.scale)
            orig_x2 = int(x2 / self.scale)
            orig_y2 = int(y2 / self.scale)
            
            self.coordinates.append((orig_x1, orig_y1, orig_x2, orig_y2))
            
            # 在显示图像上绘制矩形
            cv2.rectangle(self.image, (x1, y1), (x2, y2), (0, 255, 0), 2)
            cv2.imshow(self.window_name, self.image)
            
            # 打印原始图片的坐标
            print(f"选择的区域坐标（原始尺寸）: ({orig_x1}, {orig_y1}) -> ({orig_x2}, {orig_y2})")
            print(f"区域大小: {orig_x2-orig_x1}×{orig_y2-orig_y1} 像素")
    
    def mark_image(self, image_path):
        # 读取图像
        self.image = cv2.imread(image_path)
        if self.image is None:
            print(f"无法读取图片: {image_path}")
            return None
            
        # 保存原始尺寸
        self.original_size = self.image.shape[:2]
        
        # 调整图像大小以适应屏幕
        screen_height = 1080  # 假设屏幕高度为1080
        if self.image.shape[0] > screen_height:
            self.scale = screen_height / self.image.shape[0]
            new_width = int(self.image.shape[1] * self.scale)
            self.image = cv2.resize(self.image, (new_width, screen_height))
        else:
            self.scale = 1.0
            
        # 打印图片信息
        print(f"\n图片信息:")
        print(f"原始尺寸: {self.original_size[1]}×{self.original_size[0]}")
        print(f"显示尺寸: {self.image.shape[1]}×{self.image.shape[0]}")
        print(f"缩放比例: {self.scale:.3f}")
            
        # 创建窗口和鼠标回调
        cv2.namedWindow(self.window_name)
        cv2.setMouseCallback(self.window_name, self.mouse_callback)
        
        # 显示图像
        cv2.imshow(self.window_name, self.image)
        print(f"\n正在标记图片: {image_path}")
        print("请用鼠标拖动选择区域，按 'q' 完成当前图片标记")
        
        # 等待按键
        while True:
            key = cv2.waitKey(1) & 0xFF
            if key == ord('q'):
                break
        
        cv2.destroyAllWindows()
        return self.coordinates

def main():
    marker = CoordinateMarker()
    
    # 定义图片路径
    real_path = "./src/example_real.jpg"
    fake_path = "./src/example_fake.png"
    
    # 检查文件是否存在
    if not os.path.exists(real_path):
        print(f"错误：找不到真实图片 ({real_path})")
        return
    if not os.path.exists(fake_path):
        print(f"错误：找不到替换图片 ({fake_path})")
        return
    
    # 标记真实图片
    print("\n=== 请在真实图片上标记区域 ===")
    real_coords = marker.mark_image(real_path)
    
    # 重置坐标器并标记替换图片
    marker = CoordinateMarker()
    print("\n=== 请在替换图片上标记区域 ===")
    fake_coords = marker.mark_image(fake_path)
    
    # 打印最终结果
    print("\n=== 标记结果 ===")
    print("真实图片区域:", real_coords)
    print("替换图片区域:", fake_coords)

if __name__ == "__main__":
    main()
