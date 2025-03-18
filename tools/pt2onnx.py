import torch
import torch.onnx
from torch import nn

# ======================
# 1. 模型加载配置
# ======================
MODEL_PATH = "your_model.pt"  # 替换为你的模型路径
OUTPUT_ONNX_PATH = "exported_model.onnx"
INPUT_SHAPE = (1, 3, 224, 224)  # 根据你的模型输入形状修改
DEVICE = "cuda" if torch.cuda.is_available() else "cpu"

# ======================
# 2. 定义模型类（必须与原模型结构完全一致）
# ======================
# 重要：必须与训练时的模型定义完全一致！
class YourModelClass(nn.Module):
    def __init__(self):
        super().__init__()
        # 这里需要与原始模型结构完全一致
        self.backbone = nn.Sequential(
            nn.Conv2d(3, 64, kernel_size=3),
            nn.ReLU(),
            nn.MaxPool2d(2)
        )
        self.classifier = nn.Linear(64*111*111, 10)  # 示例参数，需要按实际情况修改

    def forward(self, x):
        x = self.backbone(x)
        x = x.view(x.size(0), -1)
        return self.classifier(x)

# ======================
# 3. 加载模型权重
# ======================
def load_model():
    # 初始化模型实例
    model = YourModelClass().to(DEVICE)
    
    # 加载权重（根据保存方式选择对应方法）
    if DEVICE == "cuda":
        model.load_state_dict(torch.load(MODEL_PATH))
    else:
        model.load_state_dict(torch.load(MODEL_PATH, map_location=torch.device('cpu')))
    
    model.eval()  # 必须设置为评估模式
    return model

# ======================
# 4. 导出ONNX主函数
# ======================
def export_to_onnx():
    # 加载模型
    model = load_model()
    
    # 创建虚拟输入（重要：需要与实际输入尺寸一致）
    dummy_input = torch.randn(*INPUT_SHAPE, device=DEVICE)
    
    # 动态轴配置（可选）
    dynamic_axes = {
        "input": {0: "batch_size"},  # 允许动态batch维度
        "output": {0: "batch_size"}
    }
    
    # 执行导出
    torch.onnx.export(
        model,
        dummy_input,
        OUTPUT_ONNX_PATH,
        verbose=True,
        input_names=["input"],
        output_names=["output"],
        dynamic_axes=dynamic_axes,
        opset_version=13,  # 推荐opset 13+以获得更好支持
        do_constant_folding=True,  # 优化常量折叠
        export_params=True  # 导出训练参数
    )
    print(f"Successfully exported to {OUTPUT_ONNX_PATH}")

    # ======================
    # 5. 验证导出结果（可选）
    # ======================
    try:
        import onnx
        from onnxruntime import InferenceSession
        
        # 验证ONNX模型格式
        onnx_model = onnx.load(OUTPUT_ONNX_PATH)
        onnx.checker.check_model(onnx_model)
        print("ONNX format check passed!")
        
        # 验证推理一致性
        ort_session = InferenceSession(OUTPUT_ONNX_PATH)
        
        # 生成测试输入
        test_input = torch.randn(*INPUT_SHAPE).cpu().numpy()
        
        # PyTorch推理
        with torch.no_grad():
            torch_output = model(torch.from_numpy(test_input).to(DEVICE).cpu().numpy()
        
        # ONNX Runtime推理
        ort_inputs = {ort_session.get_inputs()[0].name: test_input}
        ort_output = ort_session.run(None, ort_inputs)[0]
        
        # 结果比较
        diff = np.abs(torch_output - ort_output).max()
        print(f"Max difference: {diff:.5f}")
        assert diff < 1e-5, "输出结果差异过大！"
        
    except ImportError:
        print("验证需要安装onnx和onnxruntime: pip install onnx onnxruntime")

# ======================
# 执行导出
# ======================
if __name__ == "__main__":
    export_to_onnx()
