import concurrent.futures

import math
import util
import torch
import logging
from maze_builder.types import EnvConfig, EpisodeData
from maze_builder.env import MazeBuilderEnv
import logic.rooms.crateria
from datetime import datetime
import pickle
from maze_builder.model import Model, DoorLocalModel
from maze_builder.train_session import TrainingSession
from maze_builder.replay import ReplayBuffer
from model_average import ExponentialAverage
import io
import logic.rooms.crateria_isolated
import logic.rooms.all_rooms


logging.basicConfig(format='%(asctime)s %(message)s',
                    # level=logging.DEBUG,
                    level=logging.INFO,
                    handlers=[logging.FileHandler("train.log"),
                              logging.StreamHandler()])
# torch.autograd.set_detect_anomaly(False)
# torch.backends.cudnn.benchmark = True

start_time = datetime.now()
pickle_name = 'models/session-{}.pkl'.format(start_time.isoformat())

# devices = [torch.device('cpu')]
devices = [torch.device('cuda:1'), torch.device('cuda:0')]
num_devices = len(devices)
device = devices[0]
executor = concurrent.futures.ThreadPoolExecutor(len(devices))

num_envs = 2 ** 8
# rooms = logic.rooms.crateria_isolated.rooms
rooms = logic.rooms.all_rooms.rooms
episode_length = len(rooms)

# map_x = 32
# map_y = 32
map_x = 72
map_y = 72
env_config = EnvConfig(
    rooms=rooms,
    map_x=map_x,
    map_y=map_y,
)
envs = [MazeBuilderEnv(rooms,
                       map_x=map_x,
                       map_y=map_y,
                       num_envs=num_envs,
                       device=device,
                       must_areas_be_connected=False)
        for device in devices]

max_possible_reward = envs[0].max_reward
good_room_parts = [i for i, r in enumerate(envs[0].part_room_id.tolist()) if len(envs[0].rooms[r].door_ids) > 1]
logging.info("max_possible_reward = {}".format(max_possible_reward))


# def make_dummy_model():
#     return Model(env_config=env_config,
#                  num_doors=envs[0].num_doors,
#                  num_missing_connects=envs[0].num_missing_connects,
#                  num_room_parts=len(envs[0].good_room_parts),
#                  arity=1,
#                  map_channels=[],
#                  map_stride=[],
#                  map_kernel_size=[],
#                  map_padding=[],
#                  room_embedding_width=1,
#                  connectivity_in_width=0,
#                  connectivity_out_width=0,
#                  fc_widths=[]).to(device)
#
#
# model = make_dummy_model()
# model.state_value_lin.weight.data[:, :] = 0.0
# model.state_value_lin.bias.data[:] = 0.0
# optimizer = torch.optim.Adam(model.parameters(), lr=0.0001, betas=(0.95, 0.99), eps=1e-15)
#
# logging.info("{}".format(model))
# logging.info("{}".format(optimizer))
#
# replay_size = 2 ** 17
# session = TrainingSession(envs,
#                           model=model,
#                           optimizer=optimizer,
#                           ema_beta=0.99,
#                           replay_size=replay_size,
#                           decay_amount=0.0,
#                           sam_scale=None)
# torch.set_printoptions(linewidth=120, threshold=10000)
# #
# num_candidates = 1
# temperature = 1e-10
# explore_eps = 0.0
# gen_print_freq = 1
gen_print_freq = 1
i = 0
total_reward = 0
total_reward2 = 0
cnt_episodes = 0
logging.info("Generating data: temperature={}, num_candidates={}".format(temperature, num_candidates))
# while session.replay_buffer.size < session.replay_buffer.capacity:
while True:
    data = session.generate_round(
        episode_length=episode_length,
        num_candidates=num_candidates,
        temperature=temperature,
        explore_eps=explore_eps,
        executor=executor,
        render=False)
    # session.replay_buffer.insert(data)

    total_reward += torch.sum(data.reward.to(torch.float32)).item()
    total_reward2 += torch.sum(data.reward.to(torch.float32) ** 2).item()
    cnt_episodes += data.reward.shape[0]

    i += 1
    if i % gen_print_freq == 0:
        mean_reward = total_reward / cnt_episodes
        std_reward = math.sqrt(total_reward2 / cnt_episodes - mean_reward ** 2)
        ci_reward = std_reward * 1.96 / math.sqrt(cnt_episodes)
        logging.info("init gen {}/{}: cost={:.3f} +/- {:.3f}".format(
            session.replay_buffer.size, session.replay_buffer.capacity,
               max_possible_reward - mean_reward, ci_reward))

# pickle.dump(session, open('models/init_session.pkl', 'wb'))
# pickle.dump(session, open('models/init_session_eval.pkl', 'wb'))
# pickle.dump(session, open('models/init_session_eval.pkl', 'wb'))
# pickle.dump(session, open('models/checkpoint-3-eval.pkl', 'wb'))

# session_eval = pickle.load(open('models/init_session_eval.pkl', 'rb'))
# session_eval = pickle.load(open('models/checkpoint-3-eval.pkl', 'rb'))
# eval_batch_size = 8192
# eval_num_batches = 8
# eval_batches = []
# for i in range(eval_num_batches):
#     logging.info("Generating eval batch {} of size {}".format(i, eval_batch_size))
#     data = session_eval.replay_buffer.sample(eval_batch_size, device=device)
#     eval_batches.append(data)
# pickle.dump(eval_batches, open('models/checkpoint-3-eval_batches.pkl', 'wb'))

# session = pickle.load(open('models/init_session.pkl', 'rb'))
# eval_batches = pickle.load(open('models/eval_batches.pkl', 'rb'))
# session = pickle.load(open('models/checkpoint-3-train.pkl', 'rb'))
# eval_batches = pickle.load(open('models/checkpoint-3-eval_batches.pkl', 'rb'))
#
# session.model = DoorLocalModel(
#     env_config=env_config,
#     num_doors=envs[0].num_doors,
#     num_missing_connects=envs[0].num_missing_connects,
#     num_room_parts=len(envs[0].good_room_parts),
#     map_channels=4,
#     map_kernel_size=16,
#     connectivity_in_width=64,
#     local_widths=[256, 0],
#     global_widths=[256, 256],
#     fc_widths=[256, 256, 256],
#     alpha=2.0,
#     arity=2,
# ).to(device)
#
# session.model.state_value_lin.weight.data.zero_()
# session.model.state_value_lin.bias.data.zero_()
# session.average_parameters = ExponentialAverage(session.model.all_param_data(), beta=session.average_parameters.beta)
# session.optimizer = torch.optim.Adam(session.model.parameters(), lr=0.0001, betas=(0.9, 0.9), eps=1e-5)
# # session.optimizer = torch.optim.RMSprop(session.model.parameters(), lr=0.0004, alpha=0.8, eps=1e-5)
# # session.verbose = False
# # # session.replay_buffer.resize(2 ** 21)
# logging.info(session.model)
# logging.info(session.optimizer)
# num_params = sum(torch.prod(torch.tensor(list(param.shape))) for param in session.model.parameters())
#
#
# # session.replay_buffer.resize(2 ** 19)
# logging.info("Initial training: {} parameters, {} training examples".format(num_params, session.replay_buffer.size))
# total_loss = 0.0
# total_loss_cnt = 0
# train_round = 1
# batch_size = 2 ** 10
# train_print_freq = 2**19 / batch_size
# # train_annealing_time = 2 ** 16
# train_annealing_time = 1
# lr0 = 0.00005
# lr1 = lr0
# # lr1 = 0.00002
# session.decay_amount = 0.0
# session.average_parameters.beta = 0.9999
# session.optimizer.param_groups[0]['betas'] = (0.9, 0.9)
# session.optimizer.param_groups[0]['eps'] = 1e-8
# logging.info(session.optimizer)
# logging.info("batch_size={}, lr0={}, lr1={}, time={}, decay={}, ema_beta={}".format(
#     batch_size, lr0, lr1, train_annealing_time, session.decay_amount, session.average_parameters.beta))
# for i in range(10000000):
#     frac = max(0, min(1, train_round / train_annealing_time))
#     lr = lr0 * (lr1 / lr0) ** frac
#     session.optimizer.param_groups[0]['lr'] = lr
#
#     data = session.replay_buffer.sample(batch_size, device=device)
#     with util.DelayedKeyboardInterrupt():
#         batch_loss = session.train_batch(data)
#         if not math.isnan(batch_loss):
#             total_loss += batch_loss
#             total_loss_cnt += 1
#
#     if train_round % train_print_freq == 0:
#         avg_loss = total_loss / total_loss_cnt
#         total_loss = 0.0
#         total_loss_cnt = 0
#
#         total_eval_loss = 0.0
#         # logging.info("Computing eval")
#         with torch.no_grad():
#             with session.average_parameters.average_parameters(session.model.all_param_data()):
#                 for eval_data in eval_batches:
#                     total_eval_loss += session.eval_batch(eval_data)
#         avg_eval_loss = total_eval_loss / len(eval_batches)
#
#         logging.info("init train {}: loss={:.6f}, eval={:.6f}, frac={:.5f}".format(train_round, avg_loss, avg_eval_loss, frac))
#     train_round += 1















# pickle.dump(session, open('models/init_train.pkl', 'wb'))
# pickle.dump(session, open('models/checkpoint-1-eval.pkl', 'wb'))
# session = pickle.load(open('models/init_train.pkl', 'rb'))
# session = pickle.load(open('models/session-2022-03-29T15:40:57.320430.pkl-bk23', 'rb'))
# session = pickle.load(open('models/session-2022-04-16T09:34:25.983030.pkl-b-bk6', 'rb'))
# session = pickle.load(open('models/session-2022-05-10T20:20:23.023845.pkl-b-bk7', 'rb'))
# session.envs[0].init_part_data()
# session.envs[1].init_part_data()
# session = pickle.load(open('models/session-2022-05-10T22:04:18.463473.pkl-b-bk8', 'rb'))
# session = pickle.load(open('models/session-2022-05-10T22:57:23.723125.pkl-b-bk9', 'rb'))
# session = pickle.load(open('models/checkpoint-1-train.pkl', 'rb'))
# session = pickle.load(open('models/session-2022-05-14T08:18:13.302303.pkl-b-bk10', 'rb'))
# session = pickle.load(open('models/session-2022-05-14T16:37:56.267783.pkl', 'rb'))
# session = pickle.load(open('models/init_session.pkl', 'rb'))
# session = pickle.load(open('models/session-2022-05-21T07:40:15.324154.pkl-b-bk14', 'rb'))
# session = pickle.load(open('models/session-2022-05-21T07:40:15.324154.pkl-b-bk15', 'rb'))
session = pickle.load(open('models/session-2022-05-21T07:40:15.324154.pkl-b-bk17', 'rb'))
#
# session.replay_buffer.resize(2 ** 22)
batch_size_pow0 = 12
batch_size_pow1 = 12
lr0 = 1e-5
lr1 = 1e-5
num_candidates0 = 40
num_candidates1 = 40
num_candidates = num_candidates0
temperature0 = 1.0
temperature1 = 1.0
explore_eps0 = 0.0001
explore_eps1 = 0.0001
annealing_start = 81203
annealing_time = 20
pass_factor = 2.0  # 2.0
num_gen_rounds = 1
print_freq = 16
total_reward = 0
total_loss = 0.0
total_loss_cnt = 0
total_test_loss = 0.0
total_prob = 0.0
total_round_cnt = 0
save_freq = 256
summary_freq = 512
session.decay_amount = 1.0
# session.optimizer.param_groups[0]['betas'] = (0.95, 0.99)
session.optimizer.param_groups[0]['betas'] = (0.9, 0.9)
session.average_parameters.beta = 0.999

min_door_value = max_possible_reward
total_min_door_frac = 0
torch.set_printoptions(linewidth=120, threshold=10000)
logging.info("Checkpoint path: {}".format(pickle_name))
num_params = sum(torch.prod(torch.tensor(list(param.shape))) for param in session.model.parameters())
logging.info(
    "map_x={}, map_y={}, num_envs={}, batch_size_pow1={}, pass_factor={}, lr0={}, lr1={}, num_candidates0={}, num_candidates1={}, replay_size={}/{}, num_params={}, decay_amount={}, temp0={}, temp1={}, eps0={}, eps1={}, betas={}, ema_beta={}".format(
        map_x, map_y, session.envs[0].num_envs, batch_size_pow1, pass_factor, lr0, lr1, num_candidates0, num_candidates1, session.replay_buffer.size,
        session.replay_buffer.capacity, num_params, session.decay_amount,
        temperature0, temperature1, explore_eps0, explore_eps1, session.optimizer.param_groups[0]['betas'], session.average_parameters.beta))
logging.info("Starting training")
for i in range(1000000):
    frac = max(0, min(1, (session.num_rounds - annealing_start) / annealing_time))
    num_candidates = int(num_candidates0 + (num_candidates1 - num_candidates0) * frac)
    temperature = temperature0 * (temperature1 / temperature0) ** frac
    # explore_eps = explore_eps0 * (explore_eps1 / explore_eps0) ** frac
    explore_eps = explore_eps0 + (explore_eps1 - explore_eps0) * frac
    lr = lr0 * (lr1 / lr0) ** frac
    # lr_max = lr_max0 * (lr_max1 / lr_max0) ** frac
    # lr_min = lr_min0 * (lr_min1 / lr_min0) ** frac
    batch_size_pow = int(batch_size_pow0 + frac * (batch_size_pow1 - batch_size_pow0))
    batch_size = 2 ** batch_size_pow
    session.optimizer.param_groups[0]['lr'] = lr

    for j in range(num_gen_rounds):
        data = session.generate_round(
            episode_length=episode_length,
            num_candidates=num_candidates,
            temperature=temperature,
            explore_eps=explore_eps,
            executor=executor,
            render=False)
        # randomized_insert=session.replay_buffer.size == session.replay_buffer.capacity)
        session.replay_buffer.insert(data)

        total_reward += torch.mean(data.reward.to(torch.float32))
        total_test_loss += torch.mean(data.test_loss)
        total_prob += torch.mean(data.prob)
        total_round_cnt += 1

        min_door_tmp = (max_possible_reward - torch.max(data.reward)).item()
        if min_door_tmp < min_door_value:
            min_door_value = min_door_tmp
            total_min_door_frac = 0
        if min_door_tmp == min_door_value:
            total_min_door_frac += torch.mean(
                (data.reward == max_possible_reward - min_door_value).to(torch.float32)).item()
        session.num_rounds += 1

    num_batches = max(1, int(pass_factor * num_envs * num_gen_rounds * len(devices) * episode_length / batch_size))
    for j in range(num_batches):
        # batch_frac = j / num_batches
        # lr = lr_max * (lr_min / lr_max) ** batch_frac
        data = session.replay_buffer.sample(batch_size, device=device)
        with util.DelayedKeyboardInterrupt():
            total_loss += session.train_batch(data)
            total_loss_cnt += 1
            # torch.cuda.synchronize(session.envs[0].device)

    if session.num_rounds % print_freq < num_gen_rounds:
        buffer_reward = session.replay_buffer.episode_data.reward[:session.replay_buffer.size].to(torch.float32)
        buffer_mean_reward = torch.mean(buffer_reward)
        buffer_max_reward = torch.max(session.replay_buffer.episode_data.reward[:session.replay_buffer.size])
        buffer_frac_max_reward = torch.mean(
            (session.replay_buffer.episode_data.reward[:session.replay_buffer.size] == buffer_max_reward).to(
                torch.float32))
        buffer_doors = (session.envs[0].num_doors - torch.mean(torch.sum(
            session.replay_buffer.episode_data.door_connects[:session.replay_buffer.size, :].to(torch.float32),
            dim=1))) / 2
        all_outputs = torch.cat(
            [session.replay_buffer.episode_data.door_connects[:session.replay_buffer.size, :].to(torch.float32),
             session.replay_buffer.episode_data.missing_connects[:session.replay_buffer.size, :].to(torch.float32)],
            dim=1)
        buffer_logr = -torch.sum(torch.log(torch.mean(all_outputs, dim=0)))

        buffer_test_loss = torch.mean(session.replay_buffer.episode_data.test_loss[:session.replay_buffer.size])
        buffer_prob = torch.mean(session.replay_buffer.episode_data.prob[:session.replay_buffer.size])

        new_loss = total_loss / total_loss_cnt
        new_reward = total_reward / total_round_cnt
        new_test_loss = total_test_loss / total_round_cnt
        new_prob = total_prob / total_round_cnt
        min_door_frac = total_min_door_frac / total_round_cnt
        total_reward = 0
        total_test_loss = 0.0
        total_prob = 0.0
        total_round_cnt = 0
        total_min_door_frac = 0

        buffer_is_pass = session.replay_buffer.episode_data.action[:session.replay_buffer.size, :, 0] == len(
            envs[0].rooms) - 1
        buffer_mean_pass = torch.mean(buffer_is_pass.to(torch.float32))
        buffer_mean_rooms_missing = buffer_mean_pass * len(rooms)

        logging.info(
            "{}: cost={:.3f} (min={:d}, frac={:.6f}), rooms={:.3f}, logr={:.3f} | loss={:.5f}, cost={:.3f} (min={:d}, frac={:.4f}), test={:.5f}, p={:.6f}, nc={}, f={:.5f}".format(
                session.num_rounds, max_possible_reward - buffer_mean_reward, max_possible_reward - buffer_max_reward,
                buffer_frac_max_reward,
                buffer_mean_rooms_missing,
                # buffer_doors,
                buffer_logr,
                # buffer_test_loss,
                # buffer_prob,
                new_loss,
                max_possible_reward - new_reward,
                min_door_value,
                min_door_frac,
                new_test_loss,
                new_prob,
                num_candidates,
                frac,
            ))
        total_loss = 0.0
        total_loss_cnt = 0
        min_door_value = max_possible_reward

    if session.num_rounds % save_freq < num_gen_rounds:
        with util.DelayedKeyboardInterrupt():
            # episode_data = session.replay_buffer.episode_data
            # session.replay_buffer.episode_data = None
            pickle.dump(session, open(pickle_name, 'wb'))
            # pickle.dump(session, open(pickle_name + '-b-bk17', 'wb'))
            # pickle.dump(session, open('models/session-2022-05-10T22:04:18.463473.pkl-b-bk8', 'wb'))
            # pickle.dump(session, open('models/checkpoint-2-train.pkl', 'wb'))
            # # # # # # # # # session.replay_buffer.episode_data = episode_data
            # session = pickle.load(open(pickle_name + '-bk10', 'rb'))
    if session.num_rounds % summary_freq < num_gen_rounds:
        logging.info(torch.sort(torch.sum(session.replay_buffer.episode_data.missing_connects, dim=0)))
