# 从关系到空间：基于领域层级、知识依赖与相关性的三维知识空间模型

## 摘要

本文定义 Knowledge Galaxy 当前采用的三维知识空间模型。模型中的可见实体统一为 ResearchField，知识输入仅保留层级 H、方向性知识依赖 D 与对称相关性 R。H 计算领域归属、Scope 与布局后的层级密度；D 计算依赖深度与目标半径；R 直接计算节点对的目标距离和 relatedness loss 权重。D 与 R 还共同产生节点连接度，用于诊断节点大小，并预留给最终星体亮度。三维坐标由 relatedness、radial 与 repel 三项损失联合优化，不被解释为新的知识事实。

当前 Python 实现采用固定随机种子和确定性 Adam 优化，读取 55 个 ResearchField 的人工策展输入，输出机器可读快照和可旋转的三维诊断页面。自动关系生成、正式 Galaxy Explorer、星云体积渲染与时间演化不属于当前实现。

## 一、实体的性质与关系

### 1. ResearchField

设研究领域集合为

$$
\mathcal F=\{F_1,F_2,\ldots,F_N\}.
$$

所有可见节点均为 ResearchField。Mathematics、Statistics、Machine Learning 与 Large Language Models 可以具有不同粒度，但不因此被拆成“学科”“子学科”“主题”或“研究方向”等不同实体类型。每个实体至少保存 `id`、`name` 与 `description`，并可选保存 `emergence_time`。出现时间目前只是元数据，不进入图计算或坐标优化。

实体自身不保存基础度、中心性、重要性、学科位置或人工径向坐标。Scope、依赖深度、连接度与坐标都从关系推导，并且只写入构建结果，不写回原始领域数据。

### 2. 层级关系 H

定义

$$
H(A,B)\in[0,1],
$$

表示 A 是较广领域，并以强度 H(A,B) 包含较窄领域 B，方向固定为 broader 到 narrower。当前定义把 H 当作严格层级，因此输入校验拒绝自环、重复边和有向环。

间接归属使用最大乘积路径：

$$
M(A,B)=
\max_{p:A\rightsquigarrow B}
\prod_{(u,v)\in p}H(u,v).
$$

由此得到领域范围

$$
\mathrm{Scope}(A)=\sum_{B\ne A}M(A,B),
$$

以及归一化形式

$$
\mathrm{Scope}_{norm}(A)=
\frac{\log(1+\mathrm{Scope}(A))}
{\log(1+N-1)}.
$$

H 只生成层级闭包、成员集合、Scope 与布局后的层级密度。它不进入依赖深度、节点对距离、目标函数或诊断节点大小。改变 H 而保持 D、R 和配置不变时，坐标与连接度必须保持不变。

### 3. 知识依赖 D

定义

$$
D(A,B)\in[0,1],
$$

表示“B 以 A 为知识基础”这一有向判断的可信强度，方向为 foundation 到 dependent。D 不表示 B 使用了多少 A 的知识，也不直接表示目标距离或目标层差。所有依赖边的目标层差均为 1，D 只控制该约束的权重。

给每个领域引入标量 $q_i$，求解

$$
q^*=\arg\min_q
\left[
\sum_{i,j}D(i,j)(q_j-q_i-1)^2
+\eta\sum_iq_i^2
\right].
$$

正则项消除整体平移自由度并使线性系统可解。随后在当前图内归一化：

$$
\hat q_i=
\frac{q_i-\min(q)}
{\max(q)-\min(q)}.
$$

依赖深度映射为目标半径：

$$
r_i^*=r_{min}+(r_{max}-r_{min})\hat q_i.
$$

D 在坐标布局中只通过这条链路产生由基础向后继的径向趋势。它不会被对称化后加入局部距离，也不会替代 R。

### 4. 对称相关性 R

定义

$$
R(A,B)\in[0,1],\qquad R(A,B)=R(B,A).
$$

R 表示两个领域在内容、方法、研究对象、文献、共享工具或实际依赖程度上的无向关联强度。D 可以帮助数据策展者判断某一对领域是否也应具有 R，但图引擎不会从 D 自动生成 R。未给出的 R 在当前稀疏输入中按零损失权重处理，它只表示没有提供相关性证据。

未来可以分别计算语义相似、论文集合重叠与双向引用联系：

$$
S_{sem}(A,B)=\frac{1+\cos(E_A,E_B)}{2},
$$

$$
S_{paper}(A,B)=
\frac{|P_A\cap P_B|}{|P_A\cup P_B|},
$$

$$
S_{cite}(A,B)=
\min\left(
1,
\frac{\log(1+C_{AB})}
{Q_{0.95}(\log(1+C))}
\right),
\quad C_{AB}=C_{A\to B}+C_{B\to A},
$$

再以三者平均作为初始组合方式。该自动数据管线尚未实现，当前 R 仍是带 provenance 的人工策展输入。

### 5. D/R 综合连接度

节点显著程度希望同时考虑有向依赖与无向相关性，但同一邻居不能因为同时存在 D 和 R 被重复相加。对无序节点对定义

$$
A_{ij}=\max\left(R(i,j),D(i,j),D(j,i)\right).
$$

节点加权连接度与归一化形式为

$$
C_i=\sum_{j\ne i}A_{ij},
$$

$$
\hat C_i=
\frac{\log(1+C_i)}
{\log(1+\max_k C_k)}.
$$

连接度不进入坐标优化。当前诊断页面以

$$
s_i=s_{min}+(s_{max}-s_{min})\hat C_i
$$

控制节点大小，最大半径不超过最小半径的 2.5 倍。最终星图可以主要把它映射为星体亮度、emissive intensity 与 halo intensity，并只轻微改变半径；这些成品材质尚未实现。

## 二、三维位置与目标函数

### 6. R 产生节点对距离

每个领域具有待求三维坐标

$$
P_i=(x_i,y_i,z_i)\in\mathbb R^3.
$$

R 直接决定节点对的目标距离：

$$
d^*_{ij}=
d_{min}+
(d_{max}-d_{min})(1-R_{ij})^\gamma,
$$

关系损失权重为

$$
w_{ij}=R_{ij}^\beta.
$$

由此定义 relatedness loss：

$$
L_{relatedness}=
\sum_{i\lt j}
w_{ij}
\left(
\lVert P_i-P_j\rVert-d^*_{ij}
\right)^2.
$$

R 越高，目标距离越短、该距离约束的权重也越高。D 不出现在这些公式中，因此改变 D 而保持 R 不变时，节点对目标距离与权重必须保持不变。

### 7. D 产生径向趋势

模型不指定某个学科为中心。在每一步优化中，由当前坐标计算几何质心

$$
O(P)=\frac{1}{N}\sum_iP_i.
$$

目标半径来自依赖深度，并形成

$$
L_{radial}=
\sum_i
\left(
\lVert P_i-O(P)\rVert-r_i^*
\right)^2.
$$

低依赖深度因而倾向内部，高依赖深度倾向外围。这里没有手工指定 Mathematics 或其他领域为语义中心，但仍采用单一几何质心作为径向参考，因此多个弱连接知识簇是否会被迫形成同心结构仍需继续检验。

### 8. 纯几何排斥

为防止节点过度塌缩，加入没有知识语义的排斥项：

$$
L_{repel}=
\sum_{i\lt j}
\frac{\varepsilon}
{(\lVert P_i-P_j\rVert+\delta)^2}.
$$

它只维持几何分离，不表示领域之间存在冲突、竞争或负相关。

### 9. 联合优化

当前总损失为

$$
L(P)=
L_{relatedness}
+\lambda_D L_{radial}
+\lambda_R L_{repel},
$$

并求

$$
P^*=\arg\min_P L(P).
$$

实现使用固定随机种子、梯度裁剪、确定性 Adam 更新与每步重新居中。配置集中在 `GraphConfiguration` 中。损失输出分别保存 `relatedness`、`radial`、`repel` 及其加权结果，便于判断局部接近、径向趋势与防塌缩项之间的冲突。

### 10. H 的布局后层级区域

坐标生成后，H 的传递成员关系可以构造领域密度：

$$
\rho_A(x)=
\sum_{B\ne A}
M(A,B)
\exp\left(
-\frac{\lVert x-P_B\rVert^2}{2\sigma_B^2}
\right),
$$

并定义

$$
\Omega_A=\{x:\rho_A(x)\ge\tau_A\}.
$$

当前图引擎在共享网格上计算密度、区域内节点和区域重叠，尚不渲染体积星云。必须保持

$$
P_X\in\Omega_A
\;\not\Rightarrow\;
H(A,X)>0.
$$

一个领域可以因为 R 形成的空间接近而穿过另一个领域的密度区域，但这不会生成新的层级归属。

## 三、计算与演示边界

代码将输入、计算与视觉演示分开。`domain` 定义 ResearchField、H、D、R、统一输入和校验；`graph_engine` 分别实现层级、依赖深度、相关性距离、连接度、目标函数、布局、层级区域与诊断；`build.py` 只串联这些纯计算模块；`export.py` 负责 JSON 边界。计算链内部优先使用 dataclass，只有 JSON 输入输出处转换为无约束字典。

`graph_engine/hierarchy.py` 不包含调色板、RGB、Hex、材质或其他演示逻辑。Diagnostic Viewer 自己保存临时 H 色彩家族配置，并明确单一颜色无法表达多重归属。未来正式星图的星云颜色与材质只属于 `apps/web`，不与诊断页面共享视觉配置。

当前图构建把节点坐标、依赖深度、目标与实际半径、Scope、连接度、H、传递归属、D、R、R 派生的布局对、层级区域与诊断指标写入 `apps/diagnostic-viewer/galaxy-data.js`。直接打开同目录的 `index.html` 即可查看演示；页面只读取这些结果，不重新推断关系或计算坐标。节点大小来自连接度，H 只影响诊断颜色，D 与 R 边可以分别显示。

三维欧氏空间无法无损保存任意复杂关系网络，因此坐标只是在当前目标函数下的近似投影。模型的最低检验包括：R 对称而 D 有方向；H 无环；H 只改变归属、Scope 和区域；D 只改变依赖深度与目标半径；R 只改变节点对距离与 relatedness loss 权重；连接度不进入坐标；固定种子复现；出现时间不影响位置；全部坐标有限。
