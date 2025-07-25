import torch
import torch.onnx
from torch import nn
from torchvision import models

# ======================
# 1. 模型加载配置
# ======================
# MODEL_PATH = "your_model.pt"  # 替换为你的模型路径
MODEL_PATH = "/data/model/resnet18_imagenet.pt" 
# OUTPUT_ONNX_PATH = "exported_model.onnx"
OUTPUT_ONNX_PATH = "/data/model/resnet18_imagenet.onnx"
INPUT_SHAPE = (1, 3, 224, 224)  # 根据你的模型输入形状修改
DEVICE = "cuda" if torch.cuda.is_available() else "cpu"

# ======================
# 2. 定义模型类（必须与原模型结构完全一致）
# ======================
# 重要：必须与训练时的模型定义完全一致！
class YourModelClass(nn.Module):
    def __init__(self, num_classes=1000):
        super().__init__()
        # 加载预定义的resnet18结构
        self.model = models.resnet18(pretrained=False)
        # 修改最后的全连接层以适应类别数（如需自定义）
        self.model.fc = nn.Linear(self.model.fc.in_features, num_classes)

    def forward(self, x):
        return self.model(x)

# ======================
# 3. 加载模型权重
# ======================
def load_model():
    # 直接加载resnet18
    #model = models.resnet18(num_classes=1000)  # 或你的类别数
    #model.load_state_dict(torch.load(MODEL_PATH, map_location=DEVICE))
    #model = model.to(DEVICE)
    #model.eval()

    model = YourModelClass(num_classes=1000).to(DEVICE)
    state_dict = torch.load(MODEL_PATH, map_location=DEVICE)
    # 给所有key加上'model.'前缀
    new_state_dict = {"model." + k if not k.startswith("model.") else k: v for k, v in state_dict.items()}
    model.load_state_dict(new_state_dict)
    model.eval()
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
        import numpy as np

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
            torch_output = model(torch.from_numpy(test_input).to(DEVICE))
            torch_output = torch_output.cpu().numpy()

        # ONNX Runtime推理
        ort_inputs = {ort_session.get_inputs()[0].name: test_input}
        ort_output = ort_session.run(None, ort_inputs)[0]

        # 结果比较
        diff = np.abs(torch_output - ort_output).max()
        print(f"Max difference: {diff:.5f}")
        assert diff < 1e-5, "输出结果差异过大！"

    except ImportError:
        print("验证需要安装onnx, onnxruntime, numpy: pip install onnx onnxruntime numpy")
    except Exception as e:
        print(f"ONNX导出验证失败: {e}")

# ======================
# 执行导出
# ======================
if __name__ == "__main__":
    export_to_onnx()
