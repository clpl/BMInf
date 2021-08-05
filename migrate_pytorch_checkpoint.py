import torch
import numpy as np
from bigmodels.models.cpm2 import CPM2, CPM2Configuration
from bigmodels.parameter import Parameter
from bigmodels.layers.transformer_block import TransformerBlock

def build_parameter(name, parameter : Parameter, ckpt):
    tensor = ckpt[name]

    v = tensor.numpy().astype(np.float32)
    scale = np.abs(v).max() / 120
    
    qv = np.round(v / scale).astype("int8")
    shape = qv.shape

    delta_rate = np.abs(qv * scale - v).max()
    print(f"{name}: {delta_rate}")
    if delta_rate > 0.05:
        v = v.astype(np.float16)
        if np.issubdtype(parameter.dtype, np.integer):
            raise TypeError("%s has low precision" % name)
        parameter.put_data(shape, v.tobytes(), 1, np.float16)
    else:
        parameter.put_data(shape, qv.tobytes(), scale, np.int8)
    
    return delta_rate
    

def build_block(ckpt, model : TransformerBlock, prefix, has_cross_attn):
    build_parameter(f"{prefix}.self_attn.layer_norm.weight", model.layer_nrom_before_self_attn.weight, ckpt)
    build_parameter(f"{prefix}.self_attn.self_attn.project.weight", model.self_attention.w_project_kqv, ckpt)
    build_parameter(f"{prefix}.self_attn.self_attn.dense.weight", model.self_attention.w_out, ckpt)

    if has_cross_attn:
        build_parameter(f"{prefix}.cross_attn.layer_norm.weight", model.layer_nrom_before_cross_attn.weight, ckpt)
        build_parameter(f"{prefix}.cross_attn.cross_attn.project_q.weight", model.cross_attention.w_project_kqv, ckpt)
        build_parameter(f"{prefix}.cross_attn.cross_attn.dense.weight", model.cross_attention.w_out, ckpt)
    
    build_parameter(f"{prefix}.ff.layer_norm.weight", model.layer_nrom_before_ff.weight, ckpt)
    build_parameter(f"{prefix}.ff.dense_relu_dense.wi_0.weight", model.dense_gelu_dense.wi_0.weight, ckpt)
    build_parameter(f"{prefix}.ff.dense_relu_dense.wi_1.weight", model.dense_gelu_dense.wi_1.weight, ckpt)
    build_parameter(f"{prefix}.ff.dense_relu_dense.wo.weight", model.dense_gelu_dense.wo.weight, ckpt)

def build_encoder(ckpt, model : CPM2):
    for i in range(24):
        build_block(ckpt, model.encoder[i], f"encoder.blocks.{i}", False)

def build_decoder(ckpt, model : CPM2):
    for i in range(24):
        build_block(ckpt, model.decoder[i], f"decoder.blocks.{i}", True) 

def build_model(ckpt, model : CPM2):
    build_parameter("word_embeds.weight", model.input_embedding.weight, ckpt) 
    build_parameter("encoder.blocks.0.self_attn.self_attn.relative_attention_bias.weight", model.encoder_position_bias.embedding.weight, ckpt)
    build_parameter("encoder.final_layernorm.weight", model.encoder_final_layer_nrom.weight, ckpt)
    build_parameter("decoder.blocks.0.self_attn.self_attn.relative_attention_bias.weight", model.decoder_position_bias.embedding.weight, ckpt)
    build_parameter("decoder.final_layernorm.weight", model.decoder_final_layer_nrom.weight, ckpt)
    build_parameter("lm_head.weight", model.lm_head.weight, ckpt)
    
    ret = []
    for i in range(24):
        ret.append(ckpt[f"decoder.blocks.{i}.cross_attn.cross_attn.project_kv.weight"].numpy())
    v = np.concatenate(ret, axis=0)
    ckpt["encoder_kv.weight"] = torch.from_numpy(v)
    build_parameter("encoder_kv.weight", model.encoder_kv.w_project_kv, ckpt)
    build_encoder(ckpt, model)
    build_decoder(ckpt, model)
    
def main():
    model = torch.load("../100000/merge.pt")
    config = CPM2Configuration()
    cpm2 = CPM2(config)
    build_model(model, cpm2)
    cpm2.dump(open("checkpoint.pt", "wb"))

if __name__ == "__main__":
    main()
    